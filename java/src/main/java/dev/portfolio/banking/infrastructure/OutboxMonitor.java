package dev.portfolio.banking.infrastructure;
import dev.portfolio.banking.application.OutboxStatus;
import dev.portfolio.banking.application.OutboxStatusReader;
import org.springframework.stereotype.Component;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.slf4j.LoggerFactory;
import java.util.concurrent.locks.ReentrantLock;

@Component
public final class OutboxMonitor implements OutboxStatusReader {
    private final JdbcTemplate db;
    private final int threshold;
    private boolean alerted;
    private final ReentrantLock checking = new ReentrantLock();
    public OutboxMonitor(JdbcTemplate db, @Value("${OUTBOX_MAX_AGE_SECONDS:60}") int threshold) {
        OutboxStatus.assess(0, 0, threshold); this.db = db; this.threshold = threshold;
    }
    @Override public OutboxStatus read() {
        return db.queryForObject("SELECT count(*), coalesce(greatest(0,floor(extract(epoch FROM(now()-min(created_at))))),0)::bigint FROM outbox WHERE published_at IS NULL",
            (rows, number) -> OutboxStatus.assess(rows.getLong(1), rows.getLong(2), threshold));
    }
    @Scheduled(fixedRate=5000)
    public void check() {
        if (!checking.tryLock()) return;
        try {
            var current = read(); var logger = LoggerFactory.getLogger(getClass());
            if (current.alert() && !alerted) logger.warn("outbox_stale pending={} oldest_age_seconds={} threshold_seconds={}", current.pending(), current.oldestAgeSeconds(), current.thresholdSeconds());
            if (!current.alert() && alerted) logger.info("outbox_recovered pending={}", current.pending());
            alerted = current.alert();
        } catch (RuntimeException ex) { LoggerFactory.getLogger(getClass()).warn("outbox_monitor_unavailable reason={}", ex.getClass().getSimpleName()); }
        finally { checking.unlock(); }
    }
}
