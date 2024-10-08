import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestRegressor
import joblib

# Load the dataset
data = pd.read_csv('data/CropData.csv')

# Separate features and target
X = data[['label', 'temperature', 'N', 'P', 'K', 'ph']]
y = data['humidity']

# Define the preprocessing steps
preprocessor = ColumnTransformer(
    transformers=[
        ('num', StandardScaler(), ['temperature', 'N', 'P', 'K', 'ph']),
        ('cat', OneHotEncoder(drop='first', sparse_output=False), ['label'])
    ])

# Create a pipeline with the preprocessor and the model
model = Pipeline([
    ('preprocessor', preprocessor),
    ('regressor', RandomForestRegressor(n_estimators=100, random_state=42))
])

# Split the data and train the model
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
model.fit(X_train, y_train)

# Save the model
joblib.dump(model, 'humidity_model.joblib')

print("Model training completed and saved as 'humidity_model.joblib'")
