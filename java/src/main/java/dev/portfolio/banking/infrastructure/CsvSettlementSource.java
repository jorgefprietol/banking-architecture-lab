package dev.portfolio.banking.infrastructure;

import dev.portfolio.banking.application.ReconciliationBatch;
import dev.portfolio.banking.domain.DomainException;
import dev.portfolio.banking.domain.Reconciliation;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;

public final class CsvSettlementSource implements ReconciliationBatch.SettlementSource {
    private final Path path;
    public CsvSettlementSource(Path path) { this.path = path; }
    public List<Reconciliation.Row> read() {
        try {
            var lines = Files.readAllLines(path);
            if (lines.isEmpty() || !lines.getFirst().equals("reference,amount_minor")) throw new DomainException("invalid_settlement_header");
            return lines.stream().skip(1).filter(line -> !line.isBlank()).map(line -> {
                var fields = line.split(",", -1);
                if (fields.length != 2 || fields[0].isBlank() || !fields[1].matches("-?[0-9]+")) throw new DomainException("invalid_settlement_row");
                try { return new Reconciliation.Row(fields[0], Long.parseLong(fields[1])); }
                catch (NumberFormatException ex) { throw new DomainException("invalid_settlement_row"); }
            }).toList();
        } catch (IOException ex) { throw new IllegalStateException("settlement_input_unavailable", ex); }
    }
}
