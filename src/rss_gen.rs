use crate::db::AdEntry;
use anyhow::Result;
use chrono::{Local, Utc};
use rss::{ChannelBuilder, Guid, ItemBuilder};

pub fn generate_rss(entries: &[AdEntry], server_ip: &str, server_port: u16) -> Result<String> {
    let mut items = Vec::new();

    for entry in entries {
        let item = ItemBuilder::default()
            .title(Some(format!("{} - {}", entry.title, entry.price)))
            .link(Some(entry.url.clone()))
            .description(Some(format!(
                "Price: {} | Title: {}",
                entry.price, entry.title
            )))
            .guid(Some(Guid {
                value: entry.ad_id.clone(),
                permalink: false,
            }))
            .pub_date(Some(entry.last_checked.with_timezone(&Local).to_rfc2822()))
            .build();
        items.push(item);
    }

    let channel = ChannelBuilder::default()
        .title("Facebook Marketplace Ad Feed")
        .link(format!("http://{}:{}/rss", server_ip, server_port))
        .description("An RSS feed to monitor new ads on Facebook Marketplace")
        .last_build_date(Some(Utc::now().with_timezone(&Local).to_rfc2822()))
        .items(items)
        .build();

    Ok(channel.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::Utc;

    #[test]
    fn test_generate_rss_empty() {
        let entries = vec![];
        let rss_xml = generate_rss(&entries, "127.0.0.1", 5000).unwrap();
        assert!(rss_xml.starts_with("<?xml version=\"1.0\""));
        assert!(rss_xml.contains("<title>Facebook Marketplace Ad Feed</title>"));
    }

    #[test]
    fn test_generate_rss_with_items() {
        let now = Utc::now();
        let entries = vec![AdEntry {
            ad_id: "id1".to_string(),
            title: "Ad 1".to_string(),
            price: "$10".to_string(),
            url: "https://example.com/1".to_string(),
            first_seen: now,
            last_checked: now,
        }];

        let rss_xml = generate_rss(&entries, "127.0.0.1", 5000).unwrap();
        assert!(rss_xml.contains("Ad 1 - $10"));
        assert!(rss_xml.contains("https://example.com/1"));
        assert!(rss_xml.contains("id1"));
    }
}
