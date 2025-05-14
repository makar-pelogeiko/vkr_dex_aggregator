package ru.dexaggregator.aggregator.controller;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.cloud.client.discovery.DiscoveryClient;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.context.request.async.DeferredResult;
import ru.dexaggregator.aggregator.dto.EstimatedSwapDTO;
import ru.dexaggregator.aggregator.dto.ResponseWrapperDTO;
import ru.dexaggregator.aggregator.dto.TestDTO;
import ru.dexaggregator.aggregator.service.ExchangeProvider;

import javax.naming.ServiceUnavailableException;
import java.net.URI;
import java.net.URISyntaxException;
import java.util.List;
import java.util.Optional;
import java.util.Set;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutionException;

@RestController
public class AggregatorController {

    @Autowired
    private DiscoveryClient discoveryClient;

    @Autowired
    private RedisTemplate<String, String> redisTemplate;

    @Autowired
    private ExchangeProvider exchangeProvider;

    @Value("${spring.redis.host:None}")
    private String redisHostName;

    public Optional<URI> serviceUrl(String tag) {
        return discoveryClient.getInstances(tag)
                .stream()
                .findFirst()
                .map(si -> si.getUri());
    }

    @CrossOrigin
    @GetMapping("/redis/{k}")
    public Set<String> getByKey(@PathVariable String k) {
        Set<String> redisSet = redisTemplate.opsForSet().members(k);
        System.out.println("redis set: " + redisSet.toString());
        return redisSet;
    }

    @CrossOrigin
    @GetMapping("/name-lb/{name}/{endpoint}")
    public TestDTO discoveryPing(@PathVariable String name, @PathVariable String endpoint) throws URISyntaxException {
        TestDTO result = exchangeProvider.callByNameAndLoadBalancer(name, endpoint);
        return result;
    }

    @CrossOrigin
    @GetMapping("/disc-next")
    public TestDTO discoveryPOJOPing() throws RestClientException, ServiceUnavailableException {
        RestTemplate restTemplate = new RestTemplate();
        URI service = serviceUrl("dex-dedust")
                .map(s -> s.resolve("/test-pojo"))
                .orElseThrow(ServiceUnavailableException::new);
        TestDTO responseDTO = restTemplate.getForObject(service, TestDTO.class);
        System.out.println("response: result=" + responseDTO.getResult() + " id=" + responseDTO.getId());
        return responseDTO;
    }

    @CrossOrigin
    @GetMapping("/simple")
    public String getSimple() {
        return "simple redisHost=" + redisHostName;
    }

    @CrossOrigin
    @GetMapping("/hard/{value}")
    public String getHard(@PathVariable String value) {
        return "value= " + value;
    }

    @CrossOrigin
    @GetMapping("/call-balanced/{name}/{point}/{count}/{dur}")
    public List<EstimatedSwapDTO> callEndpointBalancedAndParallel(@PathVariable String name, @PathVariable String point,
                                        @PathVariable int count,
                                        @PathVariable int dur) throws URISyntaxException {
        return exchangeProvider.callByNameAndLoadBalancerAndParallel(name, point, count, dur);
    }

    @CrossOrigin
    @GetMapping("/swap/{tokenIn}/{tokenOut}/{amount}")
    public DeferredResult<ResponseEntity<?>> getBestForSwapAsync(@PathVariable String tokenIn, @PathVariable String tokenOut,
                                                                 @PathVariable long amount,
                                                                 @RequestParam Optional<Long> timeout,
                                                                 @RequestParam(name = "responses") Optional<Integer> minResponses)
            throws ExecutionException, InterruptedException {
        // timeout 3 sec
        DeferredResult<ResponseEntity<?>> output = new DeferredResult<>(3000L);

        tokenIn = tokenIn.toLowerCase();
        tokenOut = tokenOut.toLowerCase();
        String pairKey = tokenIn.compareTo(tokenOut) < 0 ? (tokenIn + "-" + tokenOut) : (tokenOut + "-" + tokenIn);
        CompletableFuture<ResponseWrapperDTO<EstimatedSwapDTO>> futureMinPrice =
                exchangeProvider.getEstimatedSwapBalanced(pairKey, tokenIn, tokenOut, amount, timeout, minResponses);

        futureMinPrice
                .thenApply(result -> ResponseEntity.ok(result))
                .exceptionally(ex -> {
                    var body = new ResponseWrapperDTO<EstimatedSwapDTO>(null, ex.toString(), false);
                    return ResponseEntity.status(500).body(body);
                })
                .thenAccept(result -> output.setResult(result));

        return output;
    }
}
