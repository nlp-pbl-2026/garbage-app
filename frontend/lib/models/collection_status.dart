/// Verification of a collection stream, separate from its scheduled dates.
class CollectionStatus {
  final String status;
  final String? message;
  final String? sourceUrl;

  const CollectionStatus(this.status, {this.message, this.sourceUrl});

  bool get isUnverified => status == 'unverified';

  factory CollectionStatus.fromJson(Map<String, dynamic> json) =>
      CollectionStatus(json['status'] as String,
          message: json['message'] as String?,
          sourceUrl: json['source_url'] as String?);
}
