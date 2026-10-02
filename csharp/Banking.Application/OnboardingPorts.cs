using Banking.Domain;
namespace Banking.Application;

public sealed record OnboardingRequest(string ApplicantReference, string Currency);
public sealed record OnboardingView(string State, Guid? AccountId);
public interface IOnboardingStore
{
    Task<OnboardingView> Execute(string actor, Guid requestId, OnboardingRequest request, CancellationToken ct);
}
