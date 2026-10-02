namespace Banking.Domain;

public sealed record RiskSignal(long AmountMinor, int RecentTransfers, bool SanctionsMatch);
public sealed record RiskFinding(string Rule, bool Blocked, string Reason);
public interface IRiskRule
{
    string Id { get; }
    RiskFinding Evaluate(RiskSignal signal);
}

public sealed class SanctionsRule : IRiskRule
{
    public string Id => "sanctions";
    public RiskFinding Evaluate(RiskSignal s) => new(Id, s.SanctionsMatch, s.SanctionsMatch ? "synthetic_match" : "clear");
}

public sealed class VelocityRule : IRiskRule
{
    public string Id => "velocity";
    public RiskFinding Evaluate(RiskSignal s) => new(Id, s.RecentTransfers >= 5, s.RecentTransfers >= 5 ? "limit_reached" : "within_limit");
}

public sealed class AmountRule : IRiskRule
{
    public string Id => "amount";
    public RiskFinding Evaluate(RiskSignal s) => new(Id, s.AmountMinor > 1_000_000, s.AmountMinor > 1_000_000 ? "manual_review" : "within_limit");
}

public sealed class RiskEngine
{
    private readonly IRiskRule[] rules;
    public RiskEngine(IEnumerable<IRiskRule> plugins)
    {
        rules = plugins.OrderBy(x => x.Id, StringComparer.Ordinal).ToArray();
        if (rules.Length == 0 || rules.Select(x => x.Id).Distinct().Count() != rules.Length)
            throw new DomainException("invalid_plugins");
    }
    public IReadOnlyList<RiskFinding> Evaluate(RiskSignal signal)
    {
        if (signal.AmountMinor < 0 || signal.RecentTransfers < 0) throw new DomainException("invalid_signal");
        return rules.Select(rule => rule.Evaluate(signal)).ToArray();
    }
}
