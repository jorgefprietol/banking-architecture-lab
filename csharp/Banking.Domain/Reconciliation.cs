namespace Banking.Domain;

public sealed record SettlementRow(string Reference, long Minor);
public sealed record Discrepancy(string Reference, string Kind);

public static class Reconciliation
{
    public static IReadOnlyList<Discrepancy> Compare(IEnumerable<SettlementRow> internalRows, IEnumerable<SettlementRow> providerRows)
    {
        var ledger = internalRows.GroupBy(x => x.Reference).ToDictionary(x => x.Key, x => x.ToArray());
        var provider = providerRows.GroupBy(x => x.Reference).ToDictionary(x => x.Key, x => x.ToArray());
        var result = new List<Discrepancy>();
        foreach (var key in ledger.Keys.Union(provider.Keys).Order(StringComparer.Ordinal))
        {
            ledger.TryGetValue(key, out var left);
            provider.TryGetValue(key, out var right);
            if (left?.Length > 1 || right?.Length > 1) result.Add(new(key, "duplicate"));
            else if (left is null) result.Add(new(key, "missing_internal"));
            else if (right is null) result.Add(new(key, "missing_provider"));
            else if (left[0].Minor != right[0].Minor) result.Add(new(key, "amount_mismatch"));
        }
        return result;
    }
}
