package dev.portfolio.banking.api;

import dev.portfolio.banking.application.OnboardingStore;
import dev.portfolio.banking.domain.DomainException;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.*;
import java.util.UUID;

@RestController
public final class OnboardingController {
    private final OnboardingStore store;
    public OnboardingController(OnboardingStore store) { this.store = store; }
    @PostMapping("/api/onboarding") @ResponseStatus(HttpStatus.CREATED)
    public OnboardingStore.View execute(@RequestBody OnboardingStore.Request request,
        @RequestHeader(value="Idempotency-Key", required=false) String key, @AuthenticationPrincipal Jwt jwt) {
        UUID requestId;
        try { requestId = UUID.fromString(key); } catch (RuntimeException ex) { throw new DomainException("invalid_idempotency_key"); }
        return store.execute(jwt.getSubject(), requestId, request);
    }
}
