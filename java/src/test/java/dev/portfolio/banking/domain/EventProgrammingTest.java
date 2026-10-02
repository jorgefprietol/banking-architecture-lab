package dev.portfolio.banking.domain;

import dev.portfolio.banking.application.EventDispatcher;
import org.junit.jupiter.api.Test;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import static org.junit.jupiter.api.Assertions.*;

class EventProgrammingTest {
    @Test void newSubscribersObserveTransferWithoutChangingItsRules() {
        var source = new Account(UUID.randomUUID(), new Money(100, "USD"), 0);
        var destination = new Account(UUID.randomUUID(), new Money(0, "USD"), 0);
        var dispatcher = new EventDispatcher();
        var changes = new ArrayList<Long>(); var versions = new ArrayList<Integer>();
        dispatcher.subscribe(Account.Event.class, event -> changes.add(event.delta()));
        dispatcher.subscribe(Account.Event.class, event -> versions.add(event.version()));
        var transfer = Transfer.execute(source, destination, new Money(30, "USD"));
        dispatcher.publish(transfer.debit()); dispatcher.publish(transfer.credit());
        assertEquals(List.of(-30L, 30L), changes); assertEquals(List.of(1, 1), versions);
        assertEquals(100, source.balance().minor() + destination.balance().minor());
    }
    @Test void restoredCancellationKeepsOriginalReservationIdentity() {
        var id = UUID.randomUUID();
        var restored = Inventory.restore(7, 1, List.of(new Inventory.ReservationState(id, 3, false)));
        restored.cancel(id, 1); restored.cancel(id, 1);
        assertEquals(10, restored.available()); assertEquals(2, restored.version());
    }
}
