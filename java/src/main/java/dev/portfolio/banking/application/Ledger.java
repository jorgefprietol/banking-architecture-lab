package dev.portfolio.banking.application;

import dev.portfolio.banking.domain.Account;
import java.util.List;
import java.util.UUID;

public interface Ledger {
    record CreateAccount(UUID id, String ownerId, long openingMinor, String currency) {}
    record TransferCommand(UUID sourceId, UUID destinationId, long amountMinor, String currency) {}
    record Receipt(UUID id, UUID sourceId, UUID destinationId, long amountMinor, String currency) {}
    record AccountView(UUID id, String ownerId, long balanceMinor, String currency, int version) {}
    AccountView open(CreateAccount request);
    Receipt transfer(String actor, UUID key, TransferCommand request);
    AccountView read(UUID id, String actor, boolean admin);
    List<Account.Event> history(UUID id, String actor, boolean admin);
}
