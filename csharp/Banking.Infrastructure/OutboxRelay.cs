using Confluent.Kafka;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Npgsql;

namespace Banking.Infrastructure;

public sealed class OutboxRelay(NpgsqlDataSource db, IConfiguration config, ILogger<OutboxRelay> logger) : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        using var producer = new ProducerBuilder<string, string>(new ProducerConfig
        {
            BootstrapServers = config["KAFKA_BOOTSTRAP"],
            EnableIdempotence = true,
            Acks = Acks.All,
            MessageTimeoutMs = 5000
        }).Build();
        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                await using var connection = await db.OpenConnectionAsync(stoppingToken);
                await using var tx = await connection.BeginTransactionAsync(stoppingToken);
                var batch = new List<(Guid Id, Guid Aggregate, string Payload)>();
                await using (var command = PostgresLedger.Command(connection, tx,
                    "SELECT event_id,aggregate_id,payload::text FROM outbox WHERE published_at IS NULL ORDER BY created_at LIMIT 50 FOR UPDATE SKIP LOCKED"))
                await using (var reader = await command.ExecuteReaderAsync(stoppingToken))
                    while (await reader.ReadAsync(stoppingToken)) batch.Add((reader.GetGuid(0), reader.GetGuid(1), reader.GetString(2)));
                foreach (var item in batch)
                {
                    await producer.ProduceAsync(config["KAFKA_TOPIC"]!, new Message<string, string>
                        { Key = item.Aggregate.ToString(), Value = item.Payload }, stoppingToken);
                    await using var update = PostgresLedger.Command(connection, tx, "UPDATE outbox SET published_at=now() WHERE event_id=$1", item.Id);
                    await update.ExecuteNonQueryAsync(stoppingToken);
                }
                await tx.CommitAsync(stoppingToken);
            }
            catch (Exception ex) when (!stoppingToken.IsCancellationRequested)
            {
                logger.LogWarning(ex, "Outbox delivery deferred");
            }
            await Task.Delay(500, stoppingToken);
        }
    }
}
