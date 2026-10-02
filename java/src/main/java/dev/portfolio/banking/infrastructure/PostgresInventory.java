package dev.portfolio.banking.infrastructure;

import dev.portfolio.banking.application.InventoryStore;
import dev.portfolio.banking.domain.DomainException;
import dev.portfolio.banking.domain.Inventory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.support.TransactionTemplate;
import java.util.UUID;

public final class PostgresInventory implements InventoryStore {
    private final JdbcTemplate db;
    private final TransactionTemplate tx;
    public PostgresInventory(JdbcTemplate db, TransactionTemplate tx) { this.db = db; this.tx = tx; }
    public ProductView create(ProductRequest request) {
        new Inventory(request.stock());
        if (request.id() == null || request.id().equals(new UUID(0, 0))) throw new DomainException("invalid_product");
        if (db.update("INSERT INTO products(id,stock) VALUES(?,?) ON CONFLICT DO NOTHING", request.id(), request.stock()) != 1)
            throw new DomainException("product_exists");
        return new ProductView(request.id(), request.stock(), 0);
    }
    public ProductView read(UUID id) {
        var rows = db.query("SELECT stock,version FROM products WHERE id=?", (rs, row) -> new ProductView(id, rs.getInt("stock"), rs.getInt("version")), id);
        if (rows.isEmpty()) throw new DomainException("product_not_found");
        return rows.getFirst();
    }
    public ProductView reserve(UUID id, String actor, ReservationRequest request) {
        return mutate(id, actor, request.reservationId(), request.quantity(), request.expectedVersion(), false);
    }
    public ProductView cancel(UUID id, UUID reservationId, String actor, int expectedVersion) {
        return mutate(id, actor, reservationId, 0, expectedVersion, true);
    }
    private ProductView mutate(UUID id, String actor, UUID reservationId, int quantity, int expectedVersion, boolean cancel) {
        return tx.execute(status -> {
            var products = db.query("SELECT stock,version FROM products WHERE id=? FOR UPDATE",
                (rs, row) -> new ProductView(id, rs.getInt("stock"), rs.getInt("version")), id);
            if (products.isEmpty()) throw new DomainException("product_not_found");
            var product = products.getFirst();
            var history = db.query("SELECT id,quantity,cancelled,actor FROM reservations WHERE product_id=?", (rs, row) -> {
                var existingId = rs.getObject("id", UUID.class);
                if (existingId.equals(reservationId) && !rs.getString("actor").equals(actor)) throw new DomainException("forbidden");
                return new Inventory.ReservationState(existingId, rs.getInt("quantity"), rs.getBoolean("cancelled"));
            }, id);
            var inventory = Inventory.restore(product.available(), product.version(), history);
            if (cancel) inventory.cancel(reservationId, expectedVersion);
            else inventory.reserve(reservationId, quantity, expectedVersion);
            if (inventory.version() != product.version()) {
                db.update("UPDATE products SET stock=?,version=? WHERE id=?", inventory.available(), inventory.version(), id);
                if (cancel) db.update("UPDATE reservations SET cancelled=true WHERE id=? AND product_id=?", reservationId, id);
                else if (db.update("INSERT INTO reservations(id,product_id,quantity,actor) VALUES(?,?,?,?) ON CONFLICT DO NOTHING",
                    reservationId, id, quantity, actor) != 1) throw new DomainException("reservation_conflict");
            }
            return new ProductView(id, inventory.available(), inventory.version());
        });
    }
}
