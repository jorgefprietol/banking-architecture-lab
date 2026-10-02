package dev.portfolio.banking.api;

import dev.portfolio.banking.application.InventoryStore;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.*;
import java.util.UUID;

@RestController
public final class InventoryController {
    private final InventoryStore inventory;
    public InventoryController(InventoryStore inventory) { this.inventory = inventory; }
    @PostMapping("/api/products") @ResponseStatus(HttpStatus.CREATED)
    public InventoryStore.ProductView create(@RequestBody InventoryStore.ProductRequest request) { return inventory.create(request); }
    @GetMapping("/api/products/{id}")
    public InventoryStore.ProductView read(@PathVariable UUID id) { return inventory.read(id); }
    @PostMapping("/api/products/{id}/reservations") @ResponseStatus(HttpStatus.CREATED)
    public InventoryStore.ProductView reserve(@PathVariable UUID id, @RequestBody InventoryStore.ReservationRequest request, @AuthenticationPrincipal Jwt jwt) {
        return inventory.reserve(id, jwt.getSubject(), request);
    }
    @DeleteMapping("/api/products/{id}/reservations/{reservationId}")
    public InventoryStore.ProductView cancel(@PathVariable UUID id, @PathVariable UUID reservationId, @RequestParam int expectedVersion, @AuthenticationPrincipal Jwt jwt) {
        return inventory.cancel(id, reservationId, jwt.getSubject(), expectedVersion);
    }
}
