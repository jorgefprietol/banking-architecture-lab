package dev.portfolio.banking.domain;

import java.util.HashMap;
import java.util.HashSet;
import java.util.UUID;

public final class Inventory {
    public record ReservationState(UUID id, int quantity, boolean cancelled) {}
    private final HashMap<UUID, Integer> reservations = new HashMap<>();
    private final HashSet<UUID> cancelled = new HashSet<>();
    private int available;
    private int version;
    public Inventory(int stock) {
        if (stock < 0) throw new DomainException("invalid_stock");
        available = stock;
    }
    public int available() { return available; }
    public int version() { return version; }
    public static Inventory restore(int available, int version, Iterable<ReservationState> history) {
        if (version < 0) throw new DomainException("invalid_stock");
        var inventory = new Inventory(available);
        inventory.version = version;
        for (var item : history) {
            if (item.id() == null || item.id().equals(new UUID(0, 0)) || item.quantity() <= 0 || inventory.reservations.putIfAbsent(item.id(), item.quantity()) != null)
                throw new DomainException("invalid_reservation");
            if (item.cancelled()) inventory.cancelled.add(item.id());
        }
        return inventory;
    }
    public void reserve(UUID id, int quantity, int expectedVersion) {
        if (id == null || id.equals(new UUID(0, 0)) || quantity <= 0) throw new DomainException("invalid_reservation");
        if (reservations.containsKey(id)) {
            if (reservations.get(id) != quantity || cancelled.contains(id)) throw new DomainException("reservation_conflict");
            return;
        }
        if (version != expectedVersion) throw new DomainException("version_conflict");
        if (available < quantity) throw new DomainException("insufficient_stock");
        available -= quantity;
        version++;
        reservations.put(id, quantity);
    }
    public void cancel(UUID id, int expectedVersion) {
        if (cancelled.contains(id)) return;
        if (version != expectedVersion) throw new DomainException("version_conflict");
        if (!reservations.containsKey(id)) throw new DomainException("reservation_not_found");
        available += reservations.get(id);
        cancelled.add(id);
        version++;
    }
}
