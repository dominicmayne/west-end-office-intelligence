import pandas as pd
from sklearn.linear_model import LinearRegression
import matplotlib.pyplot as plt

print("Loading dataset...")

# Load dataset
data = pd.read_csv("../data/west_end_office_data.csv")

print("Dataset loaded")

# Convert area names into numeric codes
data["area_code"] = data["area"].astype("category").cat.codes

print("Area codes created")

# Features
X = data[["year", "rent_psf", "area_code"]]

# Target variable
y = data["vacancy_rate"]

print("Training model...")

# Create model
model = LinearRegression()

# Train model
model.fit(X, y)

print("Model trained successfully")

# Generate predictions
predictions = model.predict(X)

# Add predictions to dataframe
data["predicted_vacancy"] = predictions

# Print historical predictions
print("\nPredicted Vacancy Rates:\n")

print(
    data[
        [
            "area",
            "year",
            "vacancy_rate",
            "predicted_vacancy"
        ]
    ]
)

# Future prediction section
print("\nFuture Vacancy Predictions:\n")

future_data = pd.DataFrame({
    "year": [2024, 2025, 2026, 2024, 2025, 2026],
    "rent_psf": [98, 102, 106, 132, 136, 140],
    "area_code": [3, 3, 3, 1, 1, 1]
})

# Predict future vacancy
future_predictions = model.predict(future_data)

# Add predictions
future_data["predicted_vacancy"] = future_predictions

# Add readable area names
future_data["area"] = [
    "Soho",
    "Soho",
    "Soho",
    "Mayfair",
    "Mayfair",
    "Mayfair"
]

# Display future predictions
print(
    future_data[
        [
            "area",
            "year",
            "predicted_vacancy"
        ]
    ]
)

# Create chart
plt.figure(figsize=(12,7))

# Historical data
for area in data["area"].unique():

    area_data = data[data["area"] == area]

    plt.plot(
        area_data["year"],
        area_data["vacancy_rate"],
        marker="o",
        label=f"{area} Historical"
    )

# Future forecasts
for area in future_data["area"].unique():

    area_future = future_data[future_data["area"] == area]

    plt.plot(
        area_future["year"],
        area_future["predicted_vacancy"],
        linestyle="--",
        marker="x",
        label=f"{area} Forecast"
    )

# Chart formatting
plt.title("London West End Office Vacancy Forecasts")

plt.xlabel("Year")

plt.ylabel("Vacancy Rate (%)")

plt.legend()

plt.grid(True)

# Display chart
plt.show()

# Save results for website
output = data[["area", "year", "vacancy_rate", "predicted_vacancy"]]

output.to_csv("../frontend/results.csv", index=False)

print("\nSaved results to frontend/results.csv")