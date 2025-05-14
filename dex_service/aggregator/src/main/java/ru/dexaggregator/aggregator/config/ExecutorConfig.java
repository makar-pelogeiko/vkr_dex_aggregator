package ru.dexaggregator.aggregator.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.RejectedExecutionException;
import java.util.concurrent.RejectedExecutionHandler;
import java.util.concurrent.ThreadFactory;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

@Configuration
public class ExecutorConfig {
    @Bean
    public ExecutorService executorService() {
        ThreadPoolExecutor executor = new ThreadPoolExecutor(50, 50, 0L,
                TimeUnit.MILLISECONDS,
                new LinkedBlockingQueue<>(100),
                new NamedThreadFactory("main-executor-"),
                new RejectedExecutionHandler() {
                    @Override
                    public void rejectedExecution(Runnable r, ThreadPoolExecutor executor) {
                        System.out.println("Task rejected. all threads are busy");
                        throw new RejectedExecutionException("Too many tasks in pool");
                    }
                }
        );
        executor.prestartAllCoreThreads();
        return executor;
    }

    public static class NamedThreadFactory implements ThreadFactory {

        private final ThreadFactory delegate = Executors.defaultThreadFactory();
        private final String namePrefix;
        private final AtomicInteger threadNumber = new AtomicInteger(1);

        public NamedThreadFactory(String customPrefix) {
            this.namePrefix = customPrefix;
        }

        @Override
        public Thread newThread(Runnable r) {
            Thread thread = delegate.newThread(r);
            thread.setName(namePrefix + thread.getName());
            return thread;
        }
    }
}
