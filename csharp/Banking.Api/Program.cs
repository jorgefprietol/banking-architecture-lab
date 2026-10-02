using System.Security.Claims;
using System.Text.Json;
using System.Text.Json.Serialization;
using Banking.Application;
using Banking.Domain;
using Banking.Infrastructure;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.IdentityModel.Tokens;
using Npgsql;
using OpenTelemetry.Resources;
using OpenTelemetry.Trace;

var builder = WebApplication.CreateBuilder(args);
string Required(string name) => builder.Configuration[name] ?? throw new InvalidOperationException($"Missing {name}");
builder.Services.AddSingleton(NpgsqlDataSource.Create(Required("DB_CONNECTION")));
builder.Services.AddScoped<ILedger, PostgresLedger>();
builder.Services.AddScoped<Payments>();
builder.Services.AddScoped<IInventoryStore, PostgresInventory>();
builder.Services.AddSingleton<IIdentityCheck, SyntheticIdentity>();
builder.Services.AddScoped<IOnboardingStore, PostgresOnboarding>();
builder.Services.AddSingleton(new RiskEngine([new AmountRule(), new SanctionsRule(), new VelocityRule()]));
builder.Services.ConfigureHttpJsonOptions(options =>
{
    options.SerializerOptions.RespectRequiredConstructorParameters = true;
    options.SerializerOptions.RespectNullableAnnotations = true;
    options.SerializerOptions.NumberHandling = JsonNumberHandling.Strict;
    options.SerializerOptions.UnmappedMemberHandling = JsonUnmappedMemberHandling.Disallow;
});
builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme).AddJwtBearer(options =>
{
    options.Authority = Required("OIDC_ISSUER");
    options.MetadataAddress = Required("OIDC_METADATA");
    options.RequireHttpsMetadata = !builder.Environment.IsDevelopment();
    options.MapInboundClaims = false;
    options.TokenValidationParameters = new TokenValidationParameters
    {
        ValidIssuer = Required("OIDC_ISSUER"),
        ValidAudience = "banking-lab",
        ClockSkew = TimeSpan.FromSeconds(15),
        NameClaimType = "sub"
    };
});
static bool HasRole(ClaimsPrincipal user, string role)
{
    var realm = user.FindFirst("realm_access")?.Value;
    if (realm is null) return false;
    using var json = JsonDocument.Parse(realm);
    return json.RootElement.GetProperty("roles").EnumerateArray().Any(x => x.GetString() == role);
}
builder.Services.AddAuthorization(options =>
{
    foreach (var role in new[] { "reader", "writer", "admin" })
        options.AddPolicy(role, policy => policy.RequireAuthenticatedUser().RequireAssertion(context => HasRole(context.User, role)));
});
builder.Logging.AddJsonConsole();
builder.Services.AddOpenTelemetry().ConfigureResource(r => r.AddService("ledger-csharp"))
    .WithTracing(t => t.AddAspNetCoreInstrumentation().AddOtlpExporter());
builder.Services.AddHostedService<OutboxRelay>();
builder.Services.AddSingleton<IOutboxStatus, PostgresOutboxStatus>();
builder.Services.AddHostedService<OutboxMonitor>();
var app = builder.Build();
app.Use(async (context, next) =>
{
    try { await next(context); }
    catch (DomainException ex)
    {
        var status = ex.Code switch
        {
            "forbidden" => 403,
            "account_not_found" or "reservation_not_found" or "product_not_found" => 404,
            "account_exists" or "product_exists" or "idempotency_conflict" or "version_conflict" or "reservation_conflict" => 409,
            _ => 422
        };
        await Results.Problem(statusCode: status, title: ex.Code, extensions: new Dictionary<string, object?> { ["code"] = ex.Code }).ExecuteAsync(context);
    }
    catch (BadHttpRequestException)
    {
        await Results.Problem(statusCode: 400, title: "invalid_request").ExecuteAsync(context);
    }
    catch (Exception ex) when (ex is not OperationCanceledException)
    {
        app.Logger.LogError(ex, "Request failed {TraceId}", context.TraceIdentifier);
        await Results.Problem(statusCode: 500, title: "internal_error").ExecuteAsync(context);
    }
});
app.UseAuthentication();
app.UseAuthorization();
app.MapGet("/health/live", () => Results.Ok(new { status = "UP" }));
app.MapGet("/health/ready", async (NpgsqlDataSource db, CancellationToken ct) =>
{
    await using var command = db.CreateCommand("SELECT version FROM schema_migrations WHERE version=1");
    return await command.ExecuteScalarAsync(ct) is not null ? Results.Ok(new { status = "UP" }) : Results.StatusCode(503);
});
app.MapPost("/api/accounts", async (CreateAccount request, ILedger ledger, CancellationToken ct) =>
    Results.Json(await ledger.Open(request, ct), statusCode: 201)).RequireAuthorization("admin");
app.MapGet("/api/operations/outbox", async (IOutboxStatus status, CancellationToken ct) => await status.Read(ct)).RequireAuthorization("admin");
app.MapGet("/api/accounts/{id:guid}", async (Guid id, ILedger ledger, ClaimsPrincipal user, CancellationToken ct) =>
    await ledger.Read(id, user.FindFirstValue("sub")!, HasRole(user, "admin"), ct)).RequireAuthorization("reader");
app.MapGet("/api/accounts/{id:guid}/events", async (Guid id, ILedger ledger, ClaimsPrincipal user, CancellationToken ct) =>
    await ledger.History(id, user.FindFirstValue("sub")!, HasRole(user, "admin"), ct)).RequireAuthorization("reader");
app.MapPost("/api/transfers", async (TransferCommand request, Payments payments, HttpContext context, CancellationToken ct) =>
{
    if (!Guid.TryParse(context.Request.Headers["Idempotency-Key"], out var key))
        throw new DomainException("invalid_idempotency_key");
    return Results.Json(await payments.Execute(context.User.FindFirstValue("sub")!, key, request, ct), statusCode: 201);
}).RequireAuthorization("writer");
app.MapPost("/api/risk/evaluate", (RiskSignal signal, RiskEngine risk) => risk.Evaluate(signal)).RequireAuthorization("writer");
app.MapPost("/api/reconciliation", (ReconciliationRequest request) =>
    Reconciliation.Compare(request.InternalRows, request.ProviderRows)).RequireAuthorization("admin");
app.MapPost("/api/products", async (ProductRequest request, IInventoryStore store, CancellationToken ct) =>
    Results.Json(await store.Create(request, ct), statusCode: 201)).RequireAuthorization("admin");
app.MapGet("/api/products/{id:guid}", async (Guid id, IInventoryStore store, CancellationToken ct) =>
    await store.Read(id, ct)).RequireAuthorization("reader");
app.MapPost("/api/products/{id:guid}/reservations", async (Guid id, ReservationRequest request, IInventoryStore store, ClaimsPrincipal user, CancellationToken ct) =>
    Results.Json(await store.Reserve(id, user.FindFirstValue("sub")!, request, ct), statusCode: 201)).RequireAuthorization("writer");
app.MapDelete("/api/products/{id:guid}/reservations/{reservationId:guid}", async (Guid id, Guid reservationId, int expectedVersion, IInventoryStore store, ClaimsPrincipal user, CancellationToken ct) =>
    await store.Cancel(id, reservationId, user.FindFirstValue("sub")!, expectedVersion, ct)).RequireAuthorization("writer");
app.MapPost("/api/onboarding", async (OnboardingRequest request, IOnboardingStore store, HttpContext context, CancellationToken ct) =>
{
    if (!Guid.TryParse(context.Request.Headers["Idempotency-Key"], out var key)) throw new DomainException("invalid_idempotency_key");
    return Results.Json(await store.Execute(context.User.FindFirstValue("sub")!, key, request, ct), statusCode: 201);
}).RequireAuthorization("writer");
app.Run();

public sealed record ReconciliationRequest(SettlementRow[] InternalRows, SettlementRow[] ProviderRows);
