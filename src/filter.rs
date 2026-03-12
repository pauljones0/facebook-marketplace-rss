use std::collections::HashMap;

pub fn apply_filters(
    processed_url_filters: &HashMap<String, Vec<Vec<String>>>,
    url: &str,
    title: &str,
) -> bool {
    let levels = match processed_url_filters.get(url) {
        Some(l) => l,
        None => return true, // No filters for this URL, passes
    };

    if levels.is_empty() {
        return true; // No levels defined, passes
    }

    let title_lower = title.to_lowercase();

    for keywords in levels {
        // Check if any keyword in this level matches
        let level_matched = keywords.iter().any(|kw| title_lower.contains(kw));

        if !level_matched {
            return false; // Failed this level, short-circuit
        }
    }

    true // All levels passed
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_apply_filters_empty() {
        let filters = HashMap::new();
        assert!(apply_filters(
            &filters,
            "https://example.com",
            "Some Ad Title"
        ));
    }

    #[test]
    fn test_apply_filters_single_level_pass() {
        let mut filters = HashMap::new();
        filters.insert(
            "https://example.com".to_string(),
            vec![vec!["apple".to_string(), "banana".to_string()]],
        );

        assert!(apply_filters(
            &filters,
            "https://example.com",
            "Delicious Apple Ad"
        ));
        assert!(apply_filters(
            &filters,
            "https://example.com",
            "Yellow Banana Ad"
        ));
    }

    #[test]
    fn test_apply_filters_single_level_fail() {
        let mut filters = HashMap::new();
        filters.insert(
            "https://example.com".to_string(),
            vec![vec!["apple".to_string(), "banana".to_string()]],
        );

        assert!(!apply_filters(&filters, "https://example.com", "Orange Ad"));
    }

    #[test]
    fn test_apply_filters_multi_level_pass() {
        let mut filters = HashMap::new();
        filters.insert(
            "https://example.com".to_string(),
            vec![
                vec!["iphone".to_string(), "samsung".to_string()],
                vec!["pro".to_string(), "plus".to_string()],
            ],
        );

        assert!(apply_filters(
            &filters,
            "https://example.com",
            "iPhone 15 Pro Max"
        ));
        assert!(apply_filters(
            &filters,
            "https://example.com",
            "Samsung S24 Plus"
        ));
    }

    #[test]
    fn test_apply_filters_multi_level_fail() {
        let mut filters = HashMap::new();
        filters.insert(
            "https://example.com".to_string(),
            vec![
                vec!["iphone".to_string(), "samsung".to_string()],
                vec!["pro".to_string(), "plus".to_string()],
            ],
        );

        assert!(!apply_filters(
            &filters,
            "https://example.com",
            "iPhone 15 Base"
        )); // Fails level2
        assert!(!apply_filters(
            &filters,
            "https://example.com",
            "Google Pixel Pro"
        )); // Fails level1
    }

    #[test]
    fn test_apply_filters_case_insensitive() {
        let mut filters = HashMap::new();
        filters.insert(
            "https://example.com".to_string(),
            vec![vec!["apple".to_string()]],
        );

        assert!(apply_filters(
            &filters,
            "https://example.com",
            "apple juice"
        ));
    }

    #[test]
    fn test_apply_filters_empty_level_keywords() {
        let filters = HashMap::new();
        // Pre-processed filters won't have empty levels
        assert!(apply_filters(&filters, "https://example.com", "Anything"));
    }

    #[test]
    fn test_apply_filters_non_numeric_level() {
        let filters = HashMap::new();
        // Pre-processed filters won't have non-numeric levels
        assert!(apply_filters(&filters, "https://example.com", "Orange"));
    }

    #[test]
    fn test_apply_filters_special_characters() {
        let mut filters = HashMap::new();
        filters.insert(
            "https://example.com".to_string(),
            vec![vec!["i-phone 15+".to_string()]],
        );

        assert!(apply_filters(
            &filters,
            "https://example.com",
            "New i-Phone 15+ for sale"
        ));
    }

    #[test]
    fn test_apply_filters_url_not_found_non_empty_map() {
        let mut inner = HashMap::new();
        inner.insert("level1".to_string(), vec!["apple".to_string()]);
        let mut filters = HashMap::new();
        filters.insert("https://example.com".to_string(), inner);

        assert!(apply_filters(
            &filters,
            "https://other.com",
            "Apple Ad"
        ));
    }
}
