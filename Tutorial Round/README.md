# IMC Prosperity — Tutorial Round Notes

## Strategy Comparison

| Category             | Emeralds                                                               | Tomatoes                                                          |
| -------------------- | ---------------------------------------------------------------------- | ----------------------------------------------------------------- |
| **Market Structure** | Fair value ~10000<br>Wide spread (9992–10008)<br>Discrete trade levels | Continuous price<br>Tight spread<br>Trades across full range      |
| **Core Edge**        | Execution / spread capture                                             | Prediction + execution                                            |
| **Strategy Type**    | Market making                                                          | Hybrid (MR + Momentum)                                            |
| **Entry Logic**      | Quote inside spread:<br>`bid = best_bid + 1`<br>`ask = best_ask - 1`   | MR: trade z-score<br>MOM: trade trend                             |
| **Adaptation**       | Adjust based on fill time:<br>fast → widen<br>slow → tighten           | Switch based on signal alignment:<br>conflict → MR<br>align → MOM |
| **Signals**          | Order book + fills                                                     | Mid, z-score, trend                                               |
| **Inventory**        | Tight control, symmetric<br>bias to unwind                             | Avoid loading against trend                                       |
| **Modeling**         | Empirical λ from trades<br>(fill timing)                               | Rolling stats (MA, std, trend)                                    |
| **Endgame**          | Stop if time_left < exit time<br>force flatten                         | Reduce exposure, follow trend                                     |
| **Key Principle**    | Best price that still fills                                            | Detect when MR fails → follow momentum                            |
