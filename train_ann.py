import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
from tensorflow.keras.models import Sequential, load_model
from tensorflow.keras.layers import Dense, Input

# ==========================================
# 1. LOAD DATA & PREPROCESSING
# ==========================================
df = pd.read_csv('dataset/recipes.csv') 

# Pisahkan fitur (X) dan target (y)
X = df.iloc[:, :-1]
y = df.iloc[:, -1]

# Ubah fitur X jadi angka dan pastikan tipe datanya adalah float32
X = pd.get_dummies(X).astype('float32').values

is_classification = False
# Coba paksa target y menjadi angka (untuk kasus regresi harga)
try:
    y = pd.to_numeric(y).astype('float32').values
except ValueError:
    # Jika error, berarti target y berupa teks/kategori asli (klasifikasi)
    is_classification = True
    le = LabelEncoder()
    y = le.fit_transform(y).astype('int32') # Pastikan formatnya int32

# Normalisasi data
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# ==========================================
# 2. SPLIT DATA
# ==========================================
X_temp, X_test, y_temp, y_test = train_test_split(X_scaled, y, test_size=0.2, random_state=42)
X_train, X_val, y_train, y_val = train_test_split(X_temp, y_temp, test_size=0.2, random_state=42)

# ==========================================
# 3. DEFINE MODEL & 4. COMPILE MODEL
# ==========================================
model = Sequential()
# Gunakan Input() secara terpisah agar tidak muncul warning di Keras versi terbaru
model.add(Input(shape=(X_train.shape[1],)))
model.add(Dense(16, activation='relu'))
model.add(Dense(8, activation='relu'))

if is_classification:
    num_classes = len(np.unique(y))
    if num_classes > 2:
        model.add(Dense(num_classes, activation='softmax'))
        model.compile(optimizer='adam', loss='sparse_categorical_crossentropy', metrics=['accuracy'])
    else:
        model.add(Dense(1, activation='sigmoid'))
        model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])
else:
    model.add(Dense(1, activation='linear'))
    model.compile(optimizer='adam', loss='mse', metrics=['mae'])

# ==========================================
# 5. FIT MODEL
# ==========================================
print("Memulai proses Fit Model...")
history = model.fit(
    X_train, y_train, 
    validation_data=(X_val, y_val),
    epochs=50, 
    batch_size=8
)

# ==========================================
# 6. EVALUATION MODEL
# ==========================================
evaluation = model.evaluate(X_val, y_val)
print(f"\nHasil Evaluasi Validasi (Loss, Metric): {evaluation}")

# ==========================================
# 7. SAVE MODEL
# ==========================================
model.save('barista_model.keras') # Format standar baru Keras (.keras lebih aman dari .h5)
print("Model berhasil disimpan sebagai 'barista_model.keras'")

# ==========================================
# 8. PREDICTION
# ==========================================
loaded_model = load_model('barista_model.keras')
predictions = loaded_model.predict(X_test)

print("\nContoh hasil prediksi pada data uji:")
for i in range(min(5, len(y_test))):
    if is_classification and len(np.unique(y)) > 2:
        pred_class = predictions[i].argmax()
        print(f"Asli (Encoded): {y_test[i]} -> Prediksi: {pred_class}")
    elif is_classification and len(np.unique(y)) == 2:
        pred_class = 1 if predictions[i][0] > 0.5 else 0
        print(f"Asli (Encoded): {y_test[i]} -> Prediksi: {pred_class}")
    else:
        print(f"Asli: {y_test[i]} -> Prediksi: {predictions[i][0]:.2f}")