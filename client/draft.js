(function() {
	var absolutePath = function(href) {
		var link = document.createElement("a");
		link.href = href;
		return (link.protocol+"//"+link.host+link.pathname+link.search+link.hash);
	}

	//TODO: define styles
	function update_volume_icons() {
		var url_to_element = {}
		$('div.thread').find('a.desktop').filter(function(i, a) {
			return a.href.endsWith('.webm') && !$(a).hasClass('volume-icon');
		}).map(function(i, a) {
			url_to_element[absolutePath(a.href)] = a;
		});
		if (webm_urls) {
			//TODO:
			$.post('http://127.0.0.1:8000/api/detect_screamers_batch', {urls: JSON.stringify(url_to_element.keys())}, function(data, status){
				results = JSON.parse(data)
				results.keys().forEach(function(url) {
					var element = url_to_element[url];
					$(element).addClass('volume-icon');
					var volume = results[url];
					//TODO: more ranges
					if (volume < -20) {
						$(element).addClass('volume-icon-silent');
						return;
					}
					if (volume < -10) {
						$(element).addClass('volume-icon-moderate');
						return;
					}
					if (volume < 0) {
						$(element).addClass('volume-icon-average');
						return;
					}
					$(element).addClass('volume-icon-loud');
				});
			})
		}
	}

	setInterval(update_screamer_icons, 30*1000);
}());