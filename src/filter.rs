use std::collections::HashMap;

pub fn apply_filters(
    url_filters: &HashMap<String, HashMap<String, Vec<String>>>,
    url: &str,
    title: &str,
) -> bool {
    let filters = match url_filters.get(url) {
        Some(f) => f,
        None => return true, // No filters for this URL, passes
    };

    if filters.is_empty() {
        return true; // No levels defined, passes
    }

    // Get levels and sort them numerically
    let mut levels: Vec<_> = filters
        .keys()
        .filter(|k| k.starts_with("level") && k[5..].chars().all(|c| c.is_ascii_digit()))
        .collect();

    levels.sort_by_key(|k| k[5..].parse::<u32>().unwrap_or(0));

    if levels.is_empty() {
        return true; // No valid levels found, passes
    }

    let title_lower = title.to_lowercase();

    for level in levels {
        let keywords = match filters.get(level) {
            Some(k) => k,
            None => continue, // Should not happen given we collected keys
        };

        if keywords.is_empty() {
            continue; // Skip empty level
        }

        // Check if any keyword in this level matches
        let level_matched = keywords
            .iter()
            .any(|kw| title_lower.contains(&kw.to_lowercase()));

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
        let mut inner = HashMap::new();
        inner.insert(
            "level1".to_string(),
            vec!["apple".to_string(), "banana".to_string()],
        );
        let mut filters = HashMap::new();
        filters.insert("https://example.com".to_string(), inner);

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
        let mut inner = HashMap::new();
        inner.insert(
            "level1".to_string(),
            vec!["apple".to_string(), "banana".to_string()],
        );
        let mut filters = HashMap::new();
        filters.insert("https://example.com".to_string(), inner);

        assert!(!apply_filters(&filters, "https://example.com", "Orange Ad"));
    }

    #[test]
    fn test_apply_filters_multi_level_pass() {
        let mut inner = HashMap::new();
        inner.insert(
            "level1".to_string(),
            vec!["iphone".to_string(), "samsung".to_string()],
        );
        inner.insert(
            "level2".to_string(),
            vec!["pro".to_string(), "plus".to_string()],
        );
        let mut filters = HashMap::new();
        filters.insert("https://example.com".to_string(), inner);

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
        let mut inner = HashMap::new();
        inner.insert(
            "level1".to_string(),
            vec!["iphone".to_string(), "samsung".to_string()],
        );
        inner.insert(
            "level2".to_string(),
            vec!["pro".to_string(), "plus".to_string()],
        );
        let mut filters = HashMap::new();
        filters.insert("https://example.com".to_string(), inner);

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
        let mut inner = HashMap::new();
        inner.insert("level1".to_string(), vec!["APPLE".to_string()]);
        let mut filters = HashMap::new();
        filters.insert("https://example.com".to_string(), inner);

        assert!(apply_filters(
            &filters,
            "https://example.com",
            "apple juice"
        ));
    }

    #[test]
    fn test_apply_filters_empty_level_keywords() {
        let mut inner = HashMap::new();
        inner.insert("level1".to_string(), vec![]);
        let mut filters = HashMap::new();
        filters.insert("https://example.com".to_string(), inner);

        assert!(apply_filters(&filters, "https://example.com", "Anything"));
    }

    #[test]
    fn test_apply_filters_non_numeric_level() {
        let mut inner = HashMap::new();
        inner.insert("levelA".to_string(), vec!["apple".to_string()]);
        let mut filters = HashMap::new();
        filters.insert("https://example.com".to_string(), inner);

        assert!(apply_filters(&filters, "https://example.com", "Orange"));
    }

    #[test]
    fn test_apply_filters_special_characters() {
        let mut inner = HashMap::new();
        inner.insert("level1".to_string(), vec!["i-phone 15+".to_string()]);
        let mut filters = HashMap::new();
        filters.insert("https://example.com".to_string(), inner);

        assert!(apply_filters(
            &filters,
            "https://example.com",
            "New i-Phone 15+ for sale"
        ));
    }
}
