package dev.portfolio.banking.application;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.function.Consumer;

/** Local programming example. Durable integration events use the outbox. */
public final class EventDispatcher {
    private final HashMap<Class<?>, List<Consumer<Object>>> handlers = new HashMap<>();
    public <T> void subscribe(Class<T> type, Consumer<T> handler) {
        handlers.computeIfAbsent(type, ignored -> new ArrayList<>()).add(message -> handler.accept(type.cast(message)));
    }
    public void publish(Object message) {
        for (var handler : List.copyOf(handlers.getOrDefault(message.getClass(), List.of()))) handler.accept(message);
    }
}
