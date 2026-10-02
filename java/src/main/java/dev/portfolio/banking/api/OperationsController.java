package dev.portfolio.banking.api;
import dev.portfolio.banking.application.OutboxStatus;
import dev.portfolio.banking.application.OutboxStatusReader;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.bind.annotation.GetMapping;

@RestController
public final class OperationsController {
    private final OutboxStatusReader monitor;
    public OperationsController(OutboxStatusReader monitor) { this.monitor = monitor; }
    @GetMapping("/api/operations/outbox") public OutboxStatus outbox() { return monitor.read(); }
}
