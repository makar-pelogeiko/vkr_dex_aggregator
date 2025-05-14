package com.example.apigateway;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.ApplicationRunner;
import org.springframework.cloud.gateway.event.RefreshRoutesEvent;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import reactor.core.publisher.Flux;

import java.time.Duration;

@Configuration
public class GatewayRouteRefresher {

    @Value("${apigateway.routes.refresh.timeout:5}")
    private long refreshTimeout;

    @Bean
    public ApplicationRunner forceRouteRefresh(ApplicationEventPublisher publisher) {
        return args -> {
            Flux.interval(Duration.ofSeconds(refreshTimeout))
                    .doOnNext(tick -> {
                        publisher.publishEvent(new RefreshRoutesEvent(this));
                    })
                    .subscribe();
        };
    }
}
