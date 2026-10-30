# ごみサポ Frontend

Flutter client for the Matsuyama City garbage classification service. The region picker covers all 58 official collection areas. The FY2026 calendar asset is generated from the same verified source as the backend; see [data guide](../docs/data.md) before building.

The search screen accepts text, one image, or both. Supported images are JPEG, PNG, GIF, and WebP up to 3 MB. It renders either a classification answer with the next collection date, or one focused clarification question. It is intentionally not a chat interface.

## Run on Chrome

```bash
flutter pub get
flutter run -d chrome --dart-define=API_BASE_URL=http://localhost:8000
```

The backend must be running and configured to call Amazon Bedrock.
