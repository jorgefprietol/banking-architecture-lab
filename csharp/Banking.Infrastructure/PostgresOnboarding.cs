using System.Security.Cryptography;
using System.Text;
using Banking.Application;
using Banking.Domain;
using Npgsql;

namespace Banking.Infrastructure;

// The eligibility provider is deliberately synthetic. No real identity data is accepted.
public sealed class SyntheticIdentity : IIdentityCheck
{
    public bool Eligible(string reference) => reference.StartsWith("verified:", StringComparison.Ordinal);
}

public sealed class PostgresOnboarding(NpgsqlDataSource db, IIdentityCheck identity) : IOnboardingStore
{
    public async Task<OnboardingView> Execute(string actor, Guid requestId, OnboardingRequest request, CancellationToken ct)
    {
        if (requestId == Guid.Empty || string.IsNullOrWhiteSpace(request.ApplicantReference) || request.ApplicantReference.Length > 128)
            throw new DomainException("invalid_applicant");
        _ = new Money(0, request.Currency);
        var fingerprint = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(request.ApplicantReference + "|" + request.Currency)));
        await using var connection = await db.OpenConnectionAsync(ct);
        await using var tx = await connection.BeginTransactionAsync(ct);
        await using (var mutex = PostgresLedger.Command(connection, tx, "SELECT pg_advisory_xact_lock(hashtextextended($1,0))", "onboarding:" + actor + ":" + requestId))
            await mutex.ExecuteNonQueryAsync(ct);
        await using (var existing = PostgresLedger.Command(connection, tx, "SELECT state,account_id,fingerprint FROM onboarding WHERE actor=$1 AND request_id=$2", actor, requestId))
        await using (var reader = await existing.ExecuteReaderAsync(ct))
        {
            if (await reader.ReadAsync(ct))
            {
                if (reader.GetString(2) != fingerprint) throw new DomainException("idempotency_conflict");
                return new(reader.GetString(0), reader.IsDBNull(1) ? null : reader.GetGuid(1));
            }
        }
        var eligible = identity.Eligible(request.ApplicantReference);
        Guid? accountId = eligible ? Guid.NewGuid() : null;
        if (accountId is Guid id)
        {
            await using var insert = PostgresLedger.Command(connection, tx, "INSERT INTO accounts(id,owner_id,currency,balance_minor,version) VALUES($1,$2,$3,0,1)", id, actor, request.Currency);
            await insert.ExecuteNonQueryAsync(ct);
            await using var opened = PostgresLedger.Command(connection, tx, "INSERT INTO account_events(event_id,account_id,version,delta,currency) VALUES($1,$2,1,0,$3)", Guid.NewGuid(), id, request.Currency);
            await opened.ExecuteNonQueryAsync(ct);
        }
        var state = eligible ? "Opened" : "Rejected";
        await using var result = PostgresLedger.Command(connection, tx, "INSERT INTO onboarding(actor,request_id,fingerprint,state,account_id) VALUES($1,$2,$3,$4,$5)",
            actor, requestId, fingerprint, state);
        result.Parameters.Add(new NpgsqlParameter { NpgsqlDbType = NpgsqlTypes.NpgsqlDbType.Uuid, Value = (object?)accountId ?? DBNull.Value });
        await result.ExecuteNonQueryAsync(ct);
        await tx.CommitAsync(ct);
        return new(state, accountId);
    }
}
