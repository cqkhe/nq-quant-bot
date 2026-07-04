# notebooks/

Espacio para investigación exploratoria (análisis de datos, prototipado de
features, estudio de resultados de backtests).

Regla del proyecto: los notebooks son para **explorar**; toda lógica que se
quiera operar debe migrarse a `src/nqbot/` con tests. Nada que viva solo en
un notebook entra al motor.

Sugerencia de arranque:

```python
import sys; sys.path.insert(0, "../src")
import pandas as pd
from nqbot.data.loader import load_ohlcv_csv

df = load_ohlcv_csv("../data/MNQ_1m_sample.csv")
df.head()
```
