package dev.portfolio.banking.api;

import dev.portfolio.banking.domain.DomainException;
import org.springframework.http.ProblemDetail;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
public class Errors {
    @ExceptionHandler(DomainException.class) ProblemDetail domain(DomainException error) {
        int status = switch (error.getMessage()) {
            case "forbidden" -> 403;
            case "account_not_found", "reservation_not_found", "product_not_found" -> 404;
            case "account_exists", "product_exists", "idempotency_conflict", "version_conflict", "reservation_conflict" -> 409;
            default -> 422;
        };
        var problem = ProblemDetail.forStatus(status);
        problem.setTitle(error.getMessage());
        problem.setProperty("code", error.getMessage());
        return problem;
    }
}
