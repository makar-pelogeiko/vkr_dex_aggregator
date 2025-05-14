package ru.dexaggregator.aggregator.dto;

import lombok.Data;

@Data
public class EstimatedSwapDTO {
    private double tokenPriceWithFee;
    private double gottenAmount;
    private double feeProportion;
    private String exchangeURL;
    private String currentURL;
}
