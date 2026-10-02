namespace Banking.Application;

public sealed record OutboxStatus(long Pending, long OldestAgeSeconds, int ThresholdSeconds, bool Alert)
{
    public static OutboxStatus Assess(long pending, long age, int threshold)
    {
        if (pending < 0 || age < 0 || threshold is < 1 or > 86400) throw new ArgumentOutOfRangeException(nameof(threshold));
        return new(pending, pending == 0 ? 0 : age, threshold, pending > 0 && age >= threshold);
    }
}
public interface IOutboxStatus { Task<OutboxStatus> Read(CancellationToken ct); }
