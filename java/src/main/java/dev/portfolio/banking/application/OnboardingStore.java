package dev.portfolio.banking.application;

import java.util.UUID;

public interface OnboardingStore {
    record Request(String applicantReference, String currency) {}
    record View(String state, UUID accountId) {}
    View execute(String actor, UUID requestId, Request request);
}
