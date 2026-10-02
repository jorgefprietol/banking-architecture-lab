using Banking.Domain;
namespace Banking.Application;

public interface ISettlementSource { IReadOnlyList<SettlementRow> Read(); }

public sealed class ReconciliationBatch(ISettlementSource ledger, ISettlementSource provider)
{
    public IReadOnlyList<Discrepancy> Execute() => Reconciliation.Compare(ledger.Read(), provider.Read());
}
