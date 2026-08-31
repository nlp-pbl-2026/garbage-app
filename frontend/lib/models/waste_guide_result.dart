class GuideSource {
  final String? title;
  final String? uri;
  final String? snippet;
  final double? score;

  const GuideSource({this.title, this.uri, this.snippet, this.score});

  factory GuideSource.fromJson(Map<String, dynamic> json) {
    return GuideSource(
      title: json['title'] as String?,
      uri: json['uri'] as String?,
      snippet: json['snippet'] as String?,
      score: (json['score'] as num?)?.toDouble(),
    );
  }
}

class WasteClassification {
  final String itemName;
  final String categoryCode;
  final String categoryName;
  final String disposalInstructions;
  final double confidence;

  const WasteClassification({
    required this.itemName,
    required this.categoryCode,
    required this.categoryName,
    required this.disposalInstructions,
    required this.confidence,
  });

  factory WasteClassification.fromJson(Map<String, dynamic> json) {
    return WasteClassification(
      itemName: json['item_name'] as String,
      categoryCode: json['category_code'] as String,
      categoryName: json['category_name'] as String,
      disposalInstructions: json['disposal_instructions'] as String,
      confidence: (json['confidence'] as num).toDouble(),
    );
  }
}

class NextCollection {
  final String date;
  final String displayDate;
  final String collectionType;

  const NextCollection({
    required this.date,
    required this.displayDate,
    required this.collectionType,
  });

  factory NextCollection.fromJson(Map<String, dynamic> json) {
    return NextCollection(
      date: json['date'] as String,
      displayDate: json['display_date'] as String,
      collectionType: json['collection_type'] as String,
    );
  }
}

class WasteGuideResult {
  final String status;
  final String? answer;
  final String? followUpQuestion;
  final String rewrittenQuery;
  final WasteClassification? classification;
  final NextCollection? nextCollection;
  final List<GuideSource> sources;

  const WasteGuideResult({
    required this.status,
    this.answer,
    this.followUpQuestion,
    required this.rewrittenQuery,
    this.classification,
    this.nextCollection,
    required this.sources,
  });

  bool get needsClarification => status == 'needs_clarification';
  bool get unableToDetermine => status == 'unable_to_determine';

  factory WasteGuideResult.fromJson(Map<String, dynamic> json) {
    return WasteGuideResult(
      status: json['status'] as String,
      answer: json['answer'] as String?,
      followUpQuestion: json['follow_up_question'] as String?,
      rewrittenQuery: json['rewritten_query'] as String,
      classification: json['classification'] == null
          ? null
          : WasteClassification.fromJson(
              json['classification'] as Map<String, dynamic>,
            ),
      nextCollection: json['next_collection'] == null
          ? null
          : NextCollection.fromJson(
              json['next_collection'] as Map<String, dynamic>,
            ),
      sources: (json['sources'] as List<dynamic>? ?? const [])
          .map((item) => GuideSource.fromJson(item as Map<String, dynamic>))
          .toList(),
    );
  }
}
