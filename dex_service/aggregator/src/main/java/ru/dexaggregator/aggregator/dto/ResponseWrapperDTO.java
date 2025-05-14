package ru.dexaggregator.aggregator.dto;

import lombok.AllArgsConstructor;
import lombok.Data;

@Data
@AllArgsConstructor
public class ResponseWrapperDTO<T> {
    private T data;
    private String desc;
    private boolean status;
}
