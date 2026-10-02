using System.Text.Json;
using System.Runtime.InteropServices;
using Banking.Domain;
using Confluent.Kafka;
using Npgsql;

string Required(string name) => Environment.GetEnvironmentVariable(name) ?? throw new InvalidOperationException($"Missing {name}");
await using var db = NpgsqlDataSource.Create(Required("DB_CONNECTION"));
using var consumer = new ConsumerBuilder<string, string>(new ConsumerConfig
{
    BootstrapServers = Required("KAFKA_BOOTSTRAP"),
    GroupId = Required("KAFKA_GROUP"),
    AutoOffsetReset = AutoOffsetReset.Earliest,
    EnableAutoCommit = false,
    EnableAutoOffsetStore = false
}).Build();
using var cancellation = new CancellationTokenSource();
Console.CancelKeyPress += (_, args) => { args.Cancel = true; cancellation.Cancel(); };
using var termination = OperatingSystem.IsLinux()
    ? PosixSignalRegistration.Create(PosixSignal.SIGTERM, context => { context.Cancel = true; cancellation.Cancel(); })
    : null;
consumer.Subscribe(Required("KAFKA_TOPIC"));
try
{
    while (!cancellation.IsCancellationRequested)
    {
        var message = consumer.Consume(cancellation.Token);
        using var json = JsonDocument.Parse(message.Message.Value);
        var root = json.RootElement;
        if (root.GetProperty("schemaVersion").GetInt32() != 1 || root.GetProperty("type").GetString() != "TransferCompleted")
            throw new InvalidOperationException("unsupported_event_contract");
        var eventId = root.GetProperty("eventId").GetGuid();
        var transferId = root.GetProperty("transferId").GetGuid();
        _ = new Money(root.GetProperty("amountMinor").GetInt64(), root.GetProperty("currency").GetString()!);
        await using var command = db.CreateCommand("INSERT INTO inbox(event_id,transfer_id,payload) VALUES($1,$2,$3::jsonb) ON CONFLICT DO NOTHING");
        command.Parameters.AddWithValue(eventId);
        command.Parameters.AddWithValue(transferId);
        command.Parameters.AddWithValue(message.Message.Value);
        await command.ExecuteNonQueryAsync(cancellation.Token);
        consumer.Commit(message);
    }
}
catch (OperationCanceledException) { }
finally { consumer.Close(); }
