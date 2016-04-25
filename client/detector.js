$(function() {
	var absolutePath = function(href) {
		var link = document.createElement("a");
		link.href = href;
		return (link.protocol+"//"+link.host+link.pathname+link.search+link.hash);
	}

	//TODO: embed CSS tag into page. Setting images for each object is really bad for page size.
	var mute = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABgAAAASCAYAAABB7B6eAAAABGdBTUEAALGPC/xhBQAAAAlwSFlzAAAOwQAADsEBuJFr7QAAABl0RVh0U29mdHdhcmUAUGFpbnQuTkVUIHYzLjUuNUmK/OAAAAFpSURBVDhPnZQ/SwNBEMXvYROrKBY2okgalRRKsLETwULExiYgpAm2gpjCLyBY+AVs9AvYKdhZaWVhYy0IloJCxEb88+Z2Ls55G7N7C4+wM7O/d5n9kyShA6glwFZoeVwdsEj4O/VNbRYWA3NxQFsNLCtY4KK9HAxoM/ZMjcSbABt/4HkDoGPy1TgDoOWBfzFWT0HAgck3w+DSS2CB2vfAu4zNK/zY5FdC4ZceaNb3J+amFX6mda89w4EOQOUf+D1zY9QQdaV1D/ydGsjtFQDDfQyuGRfzKnWnNbfpPGr4Dc61JRMEyhdLuy7SfxI9ii06Vbhs+ovCXaz0AG4UdKTwJc4/NHaosVHOZ8p5uE2cVdC62RN3c4FJ6pHqlDPIVuUvmHvc5HL9tir/VES5ATvmy1cV3mDs08R3o5jmqMpRlJPyRjVMXPYiu3DFxy7YDRgnSDa6VlgDrBmT7WCmB9T/jLuX9YSqxBj8ACsrbBBd1JhfAAAAAElFTkSuQmCC";
	var silent = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABgAAAASCAYAAABB7B6eAAAABGdBTUEAALGPC/xhBQAAAAlwSFlzAAAOwgAADsIBFShKgAAAABl0RVh0U29mdHdhcmUAUGFpbnQuTkVUIHYzLjUuNUmK/OAAAAD/SURBVDhPY2AgBvxnVGP4zzgfiMWIUU6amv+M1kCDvwPxfyAuJE0zIdX/GUOgBoMMB+EqQlqIl//PmIdmOBUt+M/YicVwCiz4zygANNAZiD2AeDUOwxEW/GfkBKoxJyU4ruExFBb+ILoCbOh/xmlQ9UmELYG4BtkQfGyYBfpQPV+ANCN+S0izAJGK/jMegVoiTn0L/jO6Qg1/RO0ggvjgP2MSEH8GYkfCFkA0nCcyHpCDiIM4wyEWgCLaAoitgDiXYDIl3mQcKhFhjJ6iqFpUGAJ98pF2ZREk6BSB+D6SJVT0ASz0/jMKAi04A7UkleLgx2rAf0Y2oAWphHMtpm4A5WQbJ4xkpwoAAAAASUVORK5CYII=";
	var moderate = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABgAAAASCAYAAABB7B6eAAAABGdBTUEAALGPC/xhBQAAAAlwSFlzAAAOwgAADsIBFShKgAAAABl0RVh0U29mdHdhcmUAUGFpbnQuTkVUIHYzLjUuNUmK/OAAAAE9SURBVDhPY2AgAvxvZFQD4vlALEaEctKUAA21BuLvQPwfiAtJ001ANdDAEKjBIMNBuIpqFgANy0MzHKsFIF+BgpAki4EaOrEYjmEBUI0WVN0XIK2I0xKgpAAQOwOxBxCvxmE43AKgPCcQm4MMBNLxUPXH8FlwDY+hsPAH0RVQQ6dB1SdB+ZuhfAsMS6CuQTYEHxtmgT4saKAW+EL5dZRaAE9FQAOPQA0VBtKGUPYEqlgANMwVauAjqA+iofxialmQBDTwMxDbQy04CbVAE2tEAyXPExnJyEHEATW8Dap3Gb5UBEp2FkBsBcTYMhjWnAxUqwM1/AoosRCd2ZDCGD1FYRQVQLWeQMxDtOEwhdCU8REt6KhXFkHDVxFowX0kS6hrAdQSQaAFZ6CWpJIcFMRoABrOBsSpQMxIjHpkNQCL1K8VyaISzgAAAABJRU5ErkJggg==";
	var loud = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABgAAAASCAYAAABB7B6eAAAABGdBTUEAALGPC/xhBQAAAAlwSFlzAAAOwgAADsIBFShKgAAAABl0RVh0U29mdHdhcmUAUGFpbnQuTkVUIHYzLjUuNUmK/OAAAAGRSURBVDhPpZTBK0RRGMVniMZCEVmwklhISSlCWUiZhZ3F1CxkahY2yk7zByhJdpasrLBiZY1SyoIoG6XsSKIsx+/TudNt5r2ZO2PqdN8379zfue++775EIuBXTCaH0AHqCbDXZwE6jX5QEa1Hzeb/JnSOtuuiM2FJYIObCjEB3dx7k2c3KATzWhk8MsCeCg2iXvSuOZmqIZi2IuAVAXiG5ftm7EOTqj8Ym0shFB1oDi2goxh4KYD7bWjCAIzL8l+pPlGd9QMeqkDd/tu4Icie/DnVp6rHtVDzHv8FaDU+pNq1Cxh1WyPGouoCY5eunxoJKHURkAuBDDim6x1vwa8NBwCZF/BFT5BVbZ1n3WS7cPefgByALzSrgGtBBxjd2dn3X/Jt4Ev2tygl+KbmHqq+VJ32A6ztrIenUNQBizzJeEcEu2dsQRnVj7UOmtvj8o6q+FQATKN2Lc75Z2p+LtQZn2VbF/ctcm1rAas14c6AuR89eyFxASk8Z2glGO6FdDLxRiH5ugEhE4C3ojxKhvh9zy9H658PylhxmAAAAABJRU5ErkJggg==";

	//TODO: handle popups?
	function update_volume_icons() {
		var url_to_element = {}
		$('div.post').find('a.desktop').filter(function(i, a) {
			return a.href.endsWith('.webm') && !$(a).hasClass('volume-icon');
		}).map(function(i, a) {
			url_to_element[absolutePath(a.href)] = a; //assume that there is no multiple records with same .webm URL
		});
		if (!$.isEmptyObject(url_to_element)) {
			//TODO:
			$.post('http://127.0.0.1:8000/api/detect_screamers_batch', {urls: JSON.stringify(Object.keys(url_to_element))}, function(data, status){
				results = JSON.parse(data)
				Object.keys(results).forEach(function(url) {
					var element = url_to_element[url];
					$(element).addClass('volume-icon');
					var volume = results[url];
					var icon = mute;
					if (volume != null) {
						if (volume < -10) {
							icon = silent;
						}
						else {
							if (volume < -5) {
								icon = moderate;
							}
							else {
								icon = loud;
							}
						}
					}
					$(element).after($('<img>', {src: icon, style: 'padding-left: 5px; height: 1em;'}));
				});
			})
		}
	}

	update_volume_icons();
	//TODO: bind update_volume_icons to ajax calls updating posts
	setInterval(update_volume_icons, 15*1000);
});