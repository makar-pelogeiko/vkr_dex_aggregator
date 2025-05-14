package ru.dexaggregator.aggregator.config;

import org.springframework.boot.ApplicationRunner;
import org.springframework.cloud.consul.discovery.ConsulDiscoveryProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.net.InetAddress;
import java.net.NetworkInterface;
import java.util.Enumeration;

@Configuration
public class IPConfig {
    @Bean
    public ApplicationRunner dynamicIpConfig(ConsulDiscoveryProperties properties) {
        return args -> {
            String ip = findExternalIp();
            properties.setIpAddress(ip);
            properties.setPreferIpAddress(true);
            System.out.println("Using IP for Consul: " + ip);
        };
    }

    private String findExternalIp() throws Exception {
        Enumeration<NetworkInterface> interfaces = NetworkInterface.getNetworkInterfaces();
        while (interfaces.hasMoreElements()) {
            NetworkInterface iface = interfaces.nextElement();
            if (!iface.isUp() || iface.isLoopback() || iface.isVirtual()) continue;

            Enumeration<InetAddress> addresses = iface.getInetAddresses();
            while (addresses.hasMoreElements()) {
                InetAddress addr = addresses.nextElement();
                if (!addr.isLoopbackAddress() && addr.getHostAddress().contains(".")) {
                    return addr.getHostAddress();
                }
            }
        }
        throw new IllegalStateException("No external IP address found.");
    }
}
