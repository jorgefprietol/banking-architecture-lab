package dev.portfolio.banking.domain;

import java.util.ArrayList;
import java.util.List;
import java.util.TreeSet;
import java.util.stream.Collectors;

public final class Reconciliation {
    private Reconciliation() {}
    public record Row(String reference, long minor) {}
    public record Discrepancy(String reference, String kind) {}
    public static List<Discrepancy> compare(List<Row> internalRows, List<Row> providerRows) {
        var ledger = internalRows.stream().collect(Collectors.groupingBy(Row::reference));
        var provider = providerRows.stream().collect(Collectors.groupingBy(Row::reference));
        var keys = new TreeSet<>(ledger.keySet());
        keys.addAll(provider.keySet());
        var result = new ArrayList<Discrepancy>();
        for (var key : keys) {
            var left = ledger.get(key);
            var right = provider.get(key);
            if ((left != null && left.size() > 1) || (right != null && right.size() > 1)) result.add(new Discrepancy(key, "duplicate"));
            else if (left == null) result.add(new Discrepancy(key, "missing_internal"));
            else if (right == null) result.add(new Discrepancy(key, "missing_provider"));
            else if (left.getFirst().minor() != right.getFirst().minor()) result.add(new Discrepancy(key, "amount_mismatch"));
        }
        return List.copyOf(result);
    }
}
