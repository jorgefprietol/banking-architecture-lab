package dev.portfolio.banking.domain;

import java.util.Comparator;
import java.util.List;

public final class RiskEngine {
    public record Signal(long amountMinor, int recentTransfers, boolean sanctionsMatch) {}
    public record Finding(String rule, boolean blocked, String reason) {}
    public interface Rule { String id(); Finding evaluate(Signal signal); }
    public static final class Sanctions implements Rule {
        public String id() { return "sanctions"; }
        public Finding evaluate(Signal s) { return new Finding(id(), s.sanctionsMatch(), s.sanctionsMatch() ? "synthetic_match" : "clear"); }
    }
    public static final class Velocity implements Rule {
        public String id() { return "velocity"; }
        public Finding evaluate(Signal s) { return new Finding(id(), s.recentTransfers() >= 5, s.recentTransfers() >= 5 ? "limit_reached" : "within_limit"); }
    }
    public static final class Amount implements Rule {
        public String id() { return "amount"; }
        public Finding evaluate(Signal s) { return new Finding(id(), s.amountMinor() > 1_000_000, s.amountMinor() > 1_000_000 ? "manual_review" : "within_limit"); }
    }
    private final List<Rule> rules;
    public RiskEngine(List<Rule> plugins) {
        rules = plugins.stream().sorted(Comparator.comparing(Rule::id)).toList();
        if (rules.isEmpty() || rules.stream().map(Rule::id).distinct().count() != rules.size())
            throw new DomainException("invalid_plugins");
    }
    public List<Finding> evaluate(Signal signal) {
        if (signal.amountMinor() < 0 || signal.recentTransfers() < 0) throw new DomainException("invalid_signal");
        return rules.stream().map(rule -> rule.evaluate(signal)).toList();
    }
}
