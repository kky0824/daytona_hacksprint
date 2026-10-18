import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv("data.csv")
df["score"][0] = 100
print(df["score"].mean())
plt.hist(df["score"])
plt.savefig("out.png")
