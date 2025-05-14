package ru.dexaggregator.aggregator.service;

import org.apache.http.client.utils.URIBuilder;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.cloud.client.discovery.DiscoveryClient;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import ru.dexaggregator.aggregator.dto.EstimatedSwapDTO;
import ru.dexaggregator.aggregator.dto.ResponseWrapperDTO;
import ru.dexaggregator.aggregator.dto.TestDTO;

import java.net.URI;
import java.net.URISyntaxException;
import java.time.Duration;
import java.util.Comparator;
import java.util.List;
import java.util.Optional;
import java.util.Set;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.stream.Collectors;

@Service
public class ExchangeProvider {

    //TIMEOUT_REQUEST_EXTERNAL
    @Value("${timeout.request.external:200}")
    private long timeoutToExternal;

    @Value("${min.answers:1}")
    private int minAnswers;

    @Autowired
    private DiscoveryClient discoveryClient;

    @Autowired
    private RedisTemplate<String, String> redisTemplate;

    @Autowired
    private WebClient webClient;

    @Autowired
    private ExecutorService executorService;

    private final RestTemplate restTemplate = new RestTemplate();

    public Optional<URI> serviceUrl(String tag) {
        return discoveryClient.getInstances(tag)
                .stream()
                .findFirst()
                .map(si -> si.getUri());
    }

    public Set<String> getFromRedis(String key) {
        //redisTemplate.opsForSet().add("key", "val1", "val2");
        return redisTemplate.opsForSet().members(key);
    }

    public String callByConsulSearch(String serviceName, String endpoint) {
        URI uri = serviceUrl(serviceName).map(s -> s.resolve("/" + endpoint)).get();
        System.out.println("uri to call: " + uri.toString());
        Mono<String> result = webClient.get()
                .uri(uri)
                .retrieve()
                .bodyToMono(String.class);
        String gotten = result.block();
        System.out.println("result: " + gotten);
        return gotten;
    }

    public TestDTO callByNameAndLoadBalancer(String serviceName, String endpoint) throws URISyntaxException {
        URI serviceUri = new URIBuilder().setScheme("http").setHost(serviceName).setPath("/" + endpoint).build();
        System.out.println("uri for balancer: " + serviceUri);
        Mono<TestDTO> result = webClient.get()
                .uri(serviceUri)
                .retrieve()
                .bodyToMono(TestDTO.class);
        TestDTO gotten = result.block();
        System.out.println("response: result=" + gotten.getResult() + "; id=" + gotten.getId());
        return gotten;
    }

    public List<EstimatedSwapDTO> callByNameAndLoadBalancerAndParallel(String serviceName, String endpoint,
                                                              int minCount, int durMilli) throws URISyntaxException {
        URI serviceUri = new URIBuilder().setScheme("http").setHost(serviceName).setPath("/" + endpoint).build();
        System.out.println("uri for balancer: " + serviceUri);

        List<URI> uris = List.of(serviceUri);
        // URI uri = new URI("http://dex-dedust/swap/usdt/ton/2000000");
        // List<URI> uris = List.of(uri);
        System.out.println("min count=" + minCount + "; duration millis=" + durMilli);
        Mono<List<EstimatedSwapDTO>> result = fetchWithMinResponsesOrTimeoutAsync(uris, minCount, Duration.ofMillis(durMilli), EstimatedSwapDTO.class);
        //System.out.println("response: result=" + gotten.getResult() + "; id=" + gotten.getId());
        return result.block();
    }

    public CompletableFuture<ResponseWrapperDTO<EstimatedSwapDTO>> getEstimatedSwapBalanced(String keyPair,
                                                                                            String tokenIn,
                                                                                            String tokenOut,
                                                                                            long amount,
                                                                                            Optional<Long> timeoutMilliSec,
                                                                                            Optional<Integer> minResponses) throws ExecutionException, InterruptedException {
        System.out.println("getEstimatedSwapBalanced(" + tokenIn + ", " + tokenOut + ", " + amount + ")");
        int answers = minResponses.orElse(minAnswers);
        long minTimeout = timeoutMilliSec.orElse(timeoutToExternal);
        System.out.println("minNumber=" + answers + ", duration=" + minTimeout);
        Set<String> servicesSet = redisTemplate.opsForSet().members(keyPair);
        List<URI> uris = servicesSet.stream()
                .map(name -> {
                    try {
                        return new URIBuilder()
                                .setScheme("http")
                                .setHost(name)
                                .setPath("/swap/" + tokenIn + "/" + tokenOut + "/" + amount)
                                .build();
                    } catch (URISyntaxException e) {
                        throw new RuntimeException(e);
                    }
                })
                .toList();
        System.out.println("uris: " + uris);

        CompletableFuture<List<EstimatedSwapDTO>> responses = fetchWithMinResponsesOrTimeout(uris, answers,
                Duration.ofMillis(minTimeout), EstimatedSwapDTO.class);

        CompletableFuture<ResponseWrapperDTO<EstimatedSwapDTO>> result = responses.thenApply(resp -> resp
                .stream()
                .max(Comparator.comparingDouble(EstimatedSwapDTO::getGottenAmount))
                .map(res -> new ResponseWrapperDTO<EstimatedSwapDTO>(res, "", true))
                .orElseGet(() -> new ResponseWrapperDTO<EstimatedSwapDTO>(null, "", false)));
        return result;
    }

    private <T> CompletableFuture<List<T>> fetchWithMinResponsesOrTimeout(List<URI> urls, int minCount,
                                                       Duration initialWait, Class<T> dataType) {
        CompletableFuture<List<T>> future = CompletableFuture.supplyAsync(() ->
                fetchWithMinResponsesOrTimeoutAsync(urls, minCount, initialWait, dataType).block(), executorService);

        return future;

    }

    private <T>Mono<List<T>> fetchWithMinResponsesOrTimeoutAsync(List<URI> urls, int minCount,
                                                            Duration initialWait, Class<T> dataType) {

        int minCountFixed = Math.min(urls.size(), minCount);
        Flux<T> responses = Flux.fromIterable(urls)
                .flatMap(url -> webClient.get()
                        .uri(url)
                        .retrieve()
                        .bodyToMono(dataType)
                        .timeout(Duration.ofSeconds(2)) // fail fast
                        .onErrorResume(e -> Mono.empty())
                );

        // to make only one set of http requests
        Flux<T> cached = responses.cache();

        Mono<List<T>> fastResponses = cached
                .take(initialWait)
                .collectList();

        Mono<List<T>> minNumberOfResponses = cached
                .take(minCount)
                .collectList();

        return fastResponses.flatMap(list -> {
            if (list.size() >= minCountFixed) {
                System.out.println("fast responses");
                return Mono.just(list);
            } else {
                System.out.println("minimal number of");
                return minNumberOfResponses;
            }
        });
    }
}
