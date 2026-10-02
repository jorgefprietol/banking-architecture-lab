using Banking.Application;
using Banking.Domain;
using Banking.Infrastructure;
using Xunit;

namespace Banking.Tests;

public sealed class SettlementTests
{
    [Fact]
    public void CsvAdapterPreservesDuplicatesForBusinessClassification()
    {
        var ledger = Path.GetTempFileName();
        var provider = Path.GetTempFileName();
        try
        {
            File.WriteAllText(ledger, "reference,amount_minor\na,10\nb,20\nb,20\n");
            File.WriteAllText(provider, "reference,amount_minor\na,11\nb,20\n");
            var result = new ReconciliationBatch(new CsvSettlementSource(ledger), new CsvSettlementSource(provider)).Execute();
            Assert.Equal(["amount_mismatch", "duplicate"], result.Select(x => x.Kind));
        }
        finally { File.Delete(ledger); File.Delete(provider); }
    }

    [Fact]
    public void ProviderDecimalsCannotBeSilentlyRounded()
    {
        var file = Path.GetTempFileName();
        try
        {
            File.WriteAllText(file, "reference,amount_minor\na,10.5\n");
            Assert.Throws<DomainException>(() => new CsvSettlementSource(file).Read());
        }
        finally { File.Delete(file); }
    }
}
