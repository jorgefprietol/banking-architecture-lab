using Banking.Application;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Npgsql;
namespace Banking.Infrastructure;

public sealed class PostgresOutboxStatus(NpgsqlDataSource db) : IOutboxStatus
{
    private readonly int threshold = OutboxStatus.Assess(0, 0, int.Parse(Environment.GetEnvironmentVariable("OUTBOX_MAX_AGE_SECONDS") ?? "60", System.Globalization.CultureInfo.InvariantCulture)).ThresholdSeconds;
    public async Task<OutboxStatus> Read(CancellationToken ct)
    {
        await using var command = db.CreateCommand("SELECT count(*), coalesce(greatest(0,floor(extract(epoch FROM(now()-min(created_at))))),0)::bigint FROM outbox WHERE published_at IS NULL");
        await using var reader = await command.ExecuteReaderAsync(ct); await reader.ReadAsync(ct);
        return OutboxStatus.Assess(reader.GetInt64(0), reader.GetInt64(1), threshold);
    }
}
public sealed class OutboxMonitor(IOutboxStatus status, ILogger<OutboxMonitor> logger) : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        var alerted = false;
        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                var current = await status.Read(stoppingToken);
                if (current.Alert && !alerted) logger.LogWarning("outbox_stale pending={Pending} oldest_age_seconds={Age} threshold_seconds={Threshold}", current.Pending, current.OldestAgeSeconds, current.ThresholdSeconds);
                if (!current.Alert && alerted) logger.LogInformation("outbox_recovered pending={Pending}", current.Pending);
                alerted = current.Alert;
            }
            catch (Exception ex) when (ex is not OperationCanceledException) { logger.LogWarning("outbox_monitor_unavailable reason={Reason}", ex.GetType().Name); }
            await Task.Delay(TimeSpan.FromSeconds(5), stoppingToken);
        }
    }
}
