using System.Text.Json;
using Banking.Application;
using Banking.Infrastructure;
using Xunit;
namespace Banking.Tests;

public class AuditRecoveryTests
{
    private static Dictionary<string, object?> Event() => new()
    {
        ["eventId"] = Guid.NewGuid(), ["transferId"] = Guid.NewGuid(), ["sourceId"] = Guid.NewGuid(),
        ["destinationId"] = Guid.NewGuid(), ["schemaVersion"] = 1, ["type"] = "TransferCompleted", ["amountMinor"] = 100L, ["currency"] = "USD"
    };
    [Fact] public void ValidEventPreservesIdentityAndMinorUnits()
    {
        var value = Event(); var parsed = AuditEvent.Parse(JsonSerializer.Serialize(value));
        Assert.Equal(value["eventId"], parsed.EventId); Assert.Equal(100, parsed.AmountMinor);
        Assert.Equal(parsed, AuditEvent.Parse(JsonSerializer.Serialize(value.OrderByDescending(x => x.Key).ToDictionary())));
    }
    [Theory]
    [InlineData("amountMinor", "100")][InlineData("amountMinor", 1.5)][InlineData("amountMinor", 0)]
    [InlineData("amountMinor", -1)][InlineData("amountMinor", 9000000000001L)][InlineData("currency", "BTC")]
    [InlineData("currency", null)][InlineData("schemaVersion", "1")][InlineData("schemaVersion", 2)]
    [InlineData("eventId", "bad-uuid")][InlineData("eventId", "00000000-0000-0000-0000-000000000000")]
    [InlineData("eventId", null)][InlineData("extra", true)]
    public void PoisonValuesAreRejected(string field, object? value)
    {
        var message = Event(); message[field] = value;
        Assert.Throws<InvalidAuditEvent>(() => AuditEvent.Parse(JsonSerializer.Serialize(message)));
    }
    [Theory][InlineData(null)][InlineData("{")][InlineData("[]")][InlineData("null")][InlineData("{}")]
    public void InvalidJsonAndShapeAreRejected(string? raw) => Assert.Throws<InvalidAuditEvent>(() => AuditEvent.Parse(raw));
    [Fact] public void DuplicateFieldsAndSameAccountAreRejected()
    {
        var value = Event(); var raw = JsonSerializer.Serialize(value);
        Assert.Throws<InvalidAuditEvent>(() => AuditEvent.Parse(raw[..^1] + ",\"currency\":\"USD\"}"));
        Assert.Throws<InvalidAuditEvent>(() => AuditEvent.Parse(raw + " {}"));
        value["destinationId"] = value["sourceId"];
        Assert.Throws<InvalidAuditEvent>(() => AuditEvent.Parse(JsonSerializer.Serialize(value)));
    }
    [Theory][InlineData(0, 120, false, 0)][InlineData(1, 59, false, 59)][InlineData(2, 60, true, 60)]
    public void AgeAlertHasInclusiveThreshold(long pending, long age, bool alert, long expectedAge)
    {
        var status = OutboxStatus.Assess(pending, age, 60);
        Assert.Equal(alert, status.Alert); Assert.Equal(expectedAge, status.OldestAgeSeconds);
    }
    [Theory][InlineData(0)][InlineData(86401)]
    public void InvalidThresholdRejected(int value) => Assert.Throws<ArgumentOutOfRangeException>(() => OutboxStatus.Assess(1, 0, value));
}
