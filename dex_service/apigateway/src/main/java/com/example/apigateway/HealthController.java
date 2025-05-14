package com.example.apigateway;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class HealthController {

    @Value("${spring.application.name:defaultName}")
    private String applicationName;

    @CrossOrigin
    @GetMapping("/health")
    public ResponseEntity<String> getHealth() {
        String message = "health ok " + applicationName;
        return new ResponseEntity<>(message, HttpStatus.OK);
    }
}
