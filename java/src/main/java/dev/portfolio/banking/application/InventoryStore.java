package dev.portfolio.banking.application;

import java.util.UUID;

public interface InventoryStore {
    record ProductView(UUID id, int available, int version) {}
    record ProductRequest(UUID id, int stock) {}
    record ReservationRequest(UUID reservationId, int quantity, int expectedVersion) {}
    ProductView create(ProductRequest request);
    ProductView read(UUID id);
    ProductView reserve(UUID id, String actor, ReservationRequest request);
    ProductView cancel(UUID id, UUID reservationId, String actor, int expectedVersion);
}
