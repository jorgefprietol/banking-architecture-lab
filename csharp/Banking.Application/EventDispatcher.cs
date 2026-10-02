namespace Banking.Application;

// Local programming example; durable integration events use the outbox instead.
public sealed class EventDispatcher
{
    private readonly Dictionary<Type, List<Delegate>> handlers = [];
    public void Subscribe<T>(Action<T> handler)
    {
        if (!handlers.TryGetValue(typeof(T), out var subscribers)) handlers[typeof(T)] = subscribers = [];
        subscribers.Add(handler);
    }
    public void Publish<T>(T message)
    {
        if (handlers.TryGetValue(typeof(T), out var subscribers))
            foreach (var handler in subscribers.ToArray()) ((Action<T>)handler)(message);
    }
}
