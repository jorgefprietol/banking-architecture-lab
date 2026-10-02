using System.Text.Json;
using System.Runtime.InteropServices;
using Banking.Infrastructure;
using Confluent.Kafka;
using Npgsql;
using NpgsqlTypes;

string Required(string name) => Environment.GetEnvironmentVariable(name) ?? throw new InvalidOperationException($"Missing {name}");
await using var db = NpgsqlDataSource.Create(Required("DB_CONNECTION"));
using var consumer = new ConsumerBuilder<string, string>(new ConsumerConfig
{
    BootstrapServers = Required("KAFKA_BOOTSTRAP"), GroupId = Required("KAFKA_GROUP"),
    AutoOffsetReset = AutoOffsetReset.Earliest, EnableAutoCommit = false, EnableAutoOffsetStore = false
}).Build();
using var producer = new ProducerBuilder<string, string>(new ProducerConfig
{
    BootstrapServers = Required("KAFKA_BOOTSTRAP"), EnableIdempotence = true, Acks = Acks.All, MessageTimeoutMs = 5000
}).Build();
var dlq = Required("KAFKA_DLQ_TOPIC");
using var cancellation = new CancellationTokenSource();
Console.CancelKeyPress += (_, args) => { args.Cancel = true; cancellation.Cancel(); };
using var termination = OperatingSystem.IsLinux()
    ? PosixSignalRegistration.Create(PosixSignal.SIGTERM, context => { context.Cancel = true; cancellation.Cancel(); }) : null;
consumer.Subscribe(Required("KAFKA_TOPIC"));

async Task Store(ConsumeResult<string, string> message)
{
    try
    {
        var parsed = AuditEvent.Parse(message.Message.Value);
        await using var command = db.CreateCommand("INSERT INTO inbox(event_id,transfer_id,payload) VALUES($1,$2,$3::jsonb) ON CONFLICT DO NOTHING");
        command.Parameters.AddWithValue(parsed.EventId); command.Parameters.AddWithValue(parsed.TransferId);
        command.Parameters.AddWithValue(message.Message.Value);
        if (await command.ExecuteNonQueryAsync(cancellation.Token) == 0)
        {
            await using var existing = db.CreateCommand("SELECT payload::text FROM inbox WHERE event_id=$1 OR transfer_id=$2");
            existing.Parameters.AddWithValue(parsed.EventId); existing.Parameters.AddWithValue(parsed.TransferId);
            await using var reader = await existing.ExecuteReaderAsync(cancellation.Token);
            var found = false;
            while (await reader.ReadAsync(cancellation.Token))
            {
                found = true;
                if (AuditEvent.Parse(reader.GetString(0)) != parsed) throw new InvalidAuditEvent("event_identity_conflict");
            }
            if (!found) throw new InvalidOperationException("inbox_conflict_without_record");
        }
    }
    catch (InvalidAuditEvent failure)
    {
        var id = Guid.NewGuid();
        var payload = JsonSerializer.Serialize(new { schemaVersion = 1, type = "AuditEventRejected", failureId = id,
            sourceTopic = message.Topic, sourcePartition = message.Partition.Value, sourceOffset = message.Offset.Value,
            originalKey = message.Message.Key, rawPayload = message.Message.Value, errorCode = failure.Message,
            rejectedAt = DateTimeOffset.UtcNow });
        await using var command = db.CreateCommand("INSERT INTO dead_letters(id,source_topic,source_partition,source_offset,raw_payload,error_code,payload) VALUES($1,$2,$3,$4,$5,$6,$7::jsonb) ON CONFLICT(source_topic,source_partition,source_offset) DO NOTHING");
        command.Parameters.AddWithValue(id); command.Parameters.AddWithValue(message.Topic);
        command.Parameters.AddWithValue(message.Partition.Value); command.Parameters.AddWithValue(message.Offset.Value);
        command.Parameters.Add(new NpgsqlParameter { NpgsqlDbType = NpgsqlDbType.Text, Value = (object?)message.Message.Value ?? DBNull.Value });
        command.Parameters.AddWithValue(failure.Message); command.Parameters.AddWithValue(payload);
        await command.ExecuteNonQueryAsync(cancellation.Token);
        Console.WriteLine(JsonSerializer.Serialize(new { code = "audit_event_quarantined", reason = failure.Message, topic = message.Topic, partition = message.Partition.Value, offset = message.Offset.Value }));
    }
    // The SQL inbox or quarantine is durable before advancing the source offset.
    consumer.Commit(message);
}

async Task Relay()
{
    await using var connection = await db.OpenConnectionAsync(cancellation.Token);
    await using var transaction = await connection.BeginTransactionAsync(cancellation.Token);
    await using var select = new NpgsqlCommand("SELECT id,payload::text FROM dead_letters WHERE published_at IS NULL ORDER BY rejected_at LIMIT 50 FOR UPDATE SKIP LOCKED", connection, transaction);
    var batch = new List<(Guid Id, string Payload)>();
    await using (var rows = await select.ExecuteReaderAsync(cancellation.Token))
        while (await rows.ReadAsync(cancellation.Token)) batch.Add((rows.GetGuid(0), rows.GetString(1)));
    foreach (var item in batch)
    {
        await producer.ProduceAsync(dlq, new Message<string, string> { Key = item.Id.ToString(), Value = item.Payload }, cancellation.Token);
        await using var update = new NpgsqlCommand("UPDATE dead_letters SET published_at=now() WHERE id=$1", connection, transaction);
        update.Parameters.AddWithValue(item.Id); await update.ExecuteNonQueryAsync(cancellation.Token);
    }
    await transaction.CommitAsync(cancellation.Token);
}

try
{
    while (!cancellation.IsCancellationRequested)
    {
        var message = consumer.Consume(TimeSpan.FromMilliseconds(500));
        if (message is not null) await Store(message);
        try { await Relay(); }
        catch (ProduceException<string, string>) { Console.WriteLine("{\"code\":\"audit_dlq_delivery_deferred\"}"); }
    }
}
catch (OperationCanceledException) when (cancellation.IsCancellationRequested) { }
finally { consumer.Close(); }
