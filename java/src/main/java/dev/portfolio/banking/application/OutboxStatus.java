package dev.portfolio.banking.application;
public record OutboxStatus(long pending, long oldestAgeSeconds, int thresholdSeconds, boolean alert) {
    public static OutboxStatus assess(long pending, long age, int threshold) {
        if (pending < 0 || age < 0 || threshold < 1 || threshold > 86400) throw new IllegalArgumentException("invalid_outbox_threshold");
        return new OutboxStatus(pending, pending == 0 ? 0 : age, threshold, pending > 0 && age >= threshold);
    }
}
