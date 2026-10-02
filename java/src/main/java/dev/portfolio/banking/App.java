package dev.portfolio.banking;

import dev.portfolio.banking.application.Ledger;
import dev.portfolio.banking.application.Payments;
import dev.portfolio.banking.application.InventoryStore;
import dev.portfolio.banking.application.OnboardingStore;
import dev.portfolio.banking.domain.RiskEngine;
import dev.portfolio.banking.infrastructure.AuditWorker;
import dev.portfolio.banking.infrastructure.PostgresLedger;
import dev.portfolio.banking.infrastructure.PostgresInventory;
import dev.portfolio.banking.infrastructure.PostgresOnboarding;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Bean;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.EnableScheduling;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;
import java.util.List;

@SpringBootApplication
@EnableScheduling
public class App {
    public static void main(String[] args) throws Exception {
        if ("audit".equals(System.getenv("BANK_MODE"))) { AuditWorker.run(); return; }
        SpringApplication.run(App.class, args);
    }
    @Bean Ledger ledger(JdbcTemplate jdbc, PlatformTransactionManager tx) { return new PostgresLedger(jdbc, new TransactionTemplate(tx)); }
    @Bean Payments payments(Ledger ledger) { return new Payments(ledger); }
    @Bean InventoryStore inventory(JdbcTemplate jdbc, PlatformTransactionManager tx) { return new PostgresInventory(jdbc, new TransactionTemplate(tx)); }
    @Bean OnboardingStore onboarding(JdbcTemplate jdbc, PlatformTransactionManager tx) {
        return new PostgresOnboarding(jdbc, new TransactionTemplate(tx), reference -> reference.startsWith("verified:"));
    }
    @Bean RiskEngine risk() { return new RiskEngine(List.of(new RiskEngine.Amount(), new RiskEngine.Velocity(), new RiskEngine.Sanctions())); }
}
