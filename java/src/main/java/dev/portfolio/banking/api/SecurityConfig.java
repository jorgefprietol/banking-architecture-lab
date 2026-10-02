package dev.portfolio.banking.api;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.oauth2.core.DelegatingOAuth2TokenValidator;
import org.springframework.security.oauth2.core.OAuth2Error;
import org.springframework.security.oauth2.core.OAuth2TokenValidatorResult;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.JwtValidators;
import org.springframework.security.oauth2.jwt.NimbusJwtDecoder;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationConverter;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.web.SecurityFilterChain;
import java.util.Collection;
import java.util.List;
import java.util.Map;

@Configuration
public class SecurityConfig {
    @Bean JwtDecoder decoder(@Value("${OIDC_JWKS}") String jwks, @Value("${OIDC_ISSUER}") String issuer) {
        var decoder = NimbusJwtDecoder.withJwkSetUri(jwks).build();
        decoder.setJwtValidator(new DelegatingOAuth2TokenValidator<Jwt>(JwtValidators.createDefaultWithIssuer(issuer),
            jwt -> jwt.getAudience().contains("banking-lab") ? OAuth2TokenValidatorResult.success() :
                OAuth2TokenValidatorResult.failure(new OAuth2Error("invalid_token", "invalid_audience", null))));
        return decoder;
    }
    @Bean SecurityFilterChain security(HttpSecurity http) throws Exception {
        var converter = new JwtAuthenticationConverter();
        converter.setJwtGrantedAuthoritiesConverter(jwt -> {
            Map<String, Object> realm = jwt.getClaim("realm_access");
            if (realm == null) return List.of();
            @SuppressWarnings("unchecked")
            var roles = (Collection<String>) realm.getOrDefault("roles", List.of());
            return roles.stream().map(role -> (org.springframework.security.core.GrantedAuthority)new SimpleGrantedAuthority("ROLE_" + role)).toList();
        });
        http.csrf(csrf -> csrf.disable()).sessionManagement(session -> session.sessionCreationPolicy(
            org.springframework.security.config.http.SessionCreationPolicy.STATELESS));
        http.authorizeHttpRequests(auth -> auth
            .dispatcherTypeMatchers(jakarta.servlet.DispatcherType.ERROR).permitAll()
            .requestMatchers("/health/**").permitAll()
            .requestMatchers(org.springframework.http.HttpMethod.POST, "/api/accounts", "/api/products", "/api/reconciliation").hasRole("admin")
            .requestMatchers(org.springframework.http.HttpMethod.GET, "/api/accounts/**", "/api/products/**").hasRole("reader")
            .requestMatchers(org.springframework.http.HttpMethod.DELETE, "/api/products/**").hasRole("writer")
            .requestMatchers(org.springframework.http.HttpMethod.POST, "/api/**").hasRole("writer")
            .anyRequest().denyAll());
        http.oauth2ResourceServer(oauth -> oauth.jwt(jwt -> jwt.jwtAuthenticationConverter(converter)));
        return http.build();
    }
}
