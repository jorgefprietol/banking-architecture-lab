namespace Banking.Domain;

public enum OnboardingState { Submitted, Rejected, Reserved, Opened, Compensated }
public interface IIdentityCheck { bool Eligible(string applicantReference); }
public interface IAccountProvisioner
{
    Guid Reserve(string applicantReference);
    void Activate(Guid reservation);
    void Release(Guid reservation);
}
public sealed record OnboardingResult(OnboardingState State, Guid? AccountId);

public sealed class OpenAccount(IIdentityCheck identity, IAccountProvisioner provisioner)
{
    public OnboardingResult Execute(string reference)
    {
        if (string.IsNullOrWhiteSpace(reference)) throw new DomainException("invalid_applicant");
        if (!identity.Eligible(reference)) return new(OnboardingState.Rejected, null);
        var reservation = provisioner.Reserve(reference);
        try
        {
            provisioner.Activate(reservation);
            return new(OnboardingState.Opened, reservation);
        }
        catch (Exception)
        {
            // A failed compensation propagates: callers must retry/reconcile it.
            provisioner.Release(reservation);
            return new(OnboardingState.Compensated, null);
        }
    }
}
