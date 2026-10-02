package dev.portfolio.banking.domain;

import dev.portfolio.banking.application.ReconciliationBatch;
import dev.portfolio.banking.infrastructure.CsvSettlementSource;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import static org.junit.jupiter.api.Assertions.*;

class SettlementTest {
    @TempDir Path directory;
    @Test void csvAdapterPreservesDuplicatesForBusinessClassification() throws Exception {
        var ledger = directory.resolve("ledger.csv"); var provider = directory.resolve("provider.csv");
        Files.writeString(ledger, "reference,amount_minor\na,10\nb,20\nb,20\n");
        Files.writeString(provider, "reference,amount_minor\na,11\nb,20\n");
        var result = new ReconciliationBatch(new CsvSettlementSource(ledger), new CsvSettlementSource(provider)).execute();
        assertEquals(List.of("amount_mismatch", "duplicate"), result.stream().map(Reconciliation.Discrepancy::kind).toList());
    }
    @Test void providerDecimalsCannotBeSilentlyRounded() throws Exception {
        var file = directory.resolve("provider.csv");
        Files.writeString(file, "reference,amount_minor\na,10.5\n");
        assertThrows(DomainException.class, () -> new CsvSettlementSource(file).read());
    }
}
