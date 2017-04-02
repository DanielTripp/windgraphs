<?php 
	if(!isset($is_main_page_dynamic)) {
		throw new Exception();
	}
?>
<!DOCTYPE html>
<html>
	<head>
	<script src="jquery-3.1.0.min.js"></script>
	<script src="sprintf.min.js"></script>
	<script type="text/javascript">

var WEATHER_CHANNEL_TO_LONG_MULTILINE_NAME = <?php readfile('WEATHER_CHANNEL_TO_LONG_MULTILINE_NAME.json');?>
var WEATHER_CHANNEL_TO_COLOR = <?php readfile('WEATHER_CHANNEL_TO_COLOR.json');?>

var WEATHER_CHANNEL_TO_SINGLE_LINE_NAME = {};
for(var channel in WEATHER_CHANNEL_TO_LONG_MULTILINE_NAME) {
	var multiline_name = WEATHER_CHANNEL_TO_LONG_MULTILINE_NAME[channel];
	var single_line_name = multiline_name.replace('\n', ' ');
	WEATHER_CHANNEL_TO_SINGLE_LINE_NAME[channel] = single_line_name;
}

function initialize() {
	init_gui_controls();
	update_img_from_gui_controls();
}

function init_gui_controls() {
	<?php if(!$is_main_page_dynamic) { ?>
		["#target_time_list", "#weather_check_num_hours_list", "#graph_domain_num_days_list"].forEach(function(ctrl_name) {
			var oldVal = sessionStorage.getItem(ctrl_name);
			if(oldVal != null) {
				$(ctrl_name).val(oldVal);
			}
			$(ctrl_name).change(on_gui_control_changed);
		});
	<?php } ?>
}

function on_gui_control_changed() {
	update_img_from_gui_controls();
	<?php if(!$is_main_page_dynamic) { ?>
			write_gui_control_values_to_storage();
	<?php } ?>
}

function write_gui_control_values_to_storage() {
	["#target_time_list", "#weather_check_num_hours_list", "#graph_domain_num_days_list"].forEach(function(ctrl_name) {
		sessionStorage.setItem(ctrl_name, $(ctrl_name).val());
	});
}

function update_img_from_gui_controls() {
	var target_time = $("#target_time_list").val();
	var weather_check_num_hours = $("#weather_check_num_hours_list").val();
	<?php
		if($is_main_page_dynamic) {
			echo 'var end_date = $("#end_date_field").val();';
		} else {
			echo 'var end_date = null;';
		}
	?>
	var num_days = $("#graph_domain_num_days_list").val();
	update_img(target_time, weather_check_num_hours, end_date, num_days);
}

function update_img(target_time_, weather_check_num_hours_, end_date_, num_days_) {
	var url = get_img_url(target_time_, weather_check_num_hours_, end_date_, num_days_);
	var y_scroll_pos = $(window).scrollTop();
	$("#img_graph").attr("src", "loading.gif");
	$("#p_info").html('');
	$.ajax({url:url, async:true, 
		error: function(jqXHR__, textStatus__, errorThrown__) {
			$("#img_graph").attr("src", "error.png");
			update_p_info_with_error(textStatus__, errorThrown__);
		}, 
		success: function(data__, textStatus__, jqXHR__) {
			$("#img_graph").attr("src", "");
			var png_content_base64 = data__['png'];
			var inline_img = "data:image/png;base64,"+png_content_base64;
			$("#img_graph").attr("src", inline_img);
			update_p_info(data__['channel_to_score'], data__['channel_to_num_forecasts']);
			$(window).scrollTop(y_scroll_pos);
		}
	});
}

function update_p_info_with_error(text_status_, error_thrown_) {
	var html = sprintf('<pre>%s\n%s</pre>', text_status_, error_thrown_);
	$("#p_info").html(html);
}

function update_p_info(channel_to_score_, channel_to_num_forecasts_) {
	var html = '';
	var channels = Object.keys(channel_to_score_);
	channels.sort(function(a__, b__) {
			var a_score = channel_to_score_[a__], b_score = channel_to_score_[b__];
			if(a_score == b_score) {
				return 0;
			} else if(a_score < b_score) {
				return -1;
			} else {
				return 1;
			}
		});
	html += '<table><tr><th valign="top" style="text-align:left">Forecast source</th>'
			+'<th>"Mean Squared Error" score<br>(Lower = more accurate)</th>'
			+'<th>Number of forecasts<br>present in this graph</th></tr>';
	channels.forEach(function(channel) {
		var score = channel_to_score_[channel];
		var num_forecasts = channel_to_num_forecasts_[channel];
		var channel_long_name = WEATHER_CHANNEL_TO_SINGLE_LINE_NAME[channel];
		var color = WEATHER_CHANNEL_TO_COLOR[channel];
		html += sprintf('<tr><td><font color="%s">%s</td><td style="text-align:center">%s</td><td style="text-align:center">%s</td></tr>', 
				color, channel_long_name, score, num_forecasts);
	});
	html += '</table>';
	$("#p_info").html(html);
}

function get_img_url(target_time_, weather_check_num_hours_, end_date_, num_days_) {
	<?php 
		if($is_main_page_dynamic) {
			echo 'return sprintf("get_graph_info.wsgi?target_time_of_day=%s&weather_check_num_hours_in_advance=%s&end_date=%s&num_days=%s", 
					target_time_, weather_check_num_hours_, end_date_, num_days_);';
		} else {
			echo 'return sprintf("static_graph_info/graph_info___target_time_%02d___hours_in_advance_%d___graph_domain_num_days_%d.json", 
					target_time_, weather_check_num_hours_, num_days_);';
		}
	?>
}

$(document).ready(initialize);

	</script>
	</head>
	<body>
		<h2>Wind forecasts vs. actual wind - Toronto Islands</h2>
		<br>
		<div>
			<div style="float: left;">
			What time of day do you sail? <br>
			<select id="target_time_list" required>
				<?php 
					foreach(explode("\n", file_get_contents('target_times.txt')) as $line) {
						if($line != "") {
							$hour_24_str = $line;
							$hour = intval($line); 
							if($hour > 12) {
								$display_str = sprintf("%02d:00 PM", $hour-12);
							} else {
								$display_str = sprintf("%02d:00 AM", $hour);
							}
							echo sprintf("<option value=\"$hour_24_str\">$display_str</option>\n"); 
						}
					}
				?>
			</select>
			<br>
			<br>
			When do you check the forecast? <br>
			<select id="weather_check_num_hours_list" required>
				<?php 
					foreach(explode("\n", file_get_contents('hours_in_advance.txt')) as $line) {
						if($line != "") {
							$num_hours = intval($line);
							if($num_hours < 72) {
								$display_str = sprintf("%d hours in advance", $num_hours);
							} else {
								$display_str = sprintf("%d days in advance", $num_hours/24);
							}
							echo sprintf("<option value=\"$num_hours\">$display_str</option>\n"); 
						}
					}
				?>
			</select>
			<br>
			<br>
			Show data for: <br>
			<select id="graph_domain_num_days_list" required>
				<?php 
					foreach(explode("\n", file_get_contents('graph_domain_num_days.txt')) as $line) {
						if($line != "") {
							$graph_domain_num_days = intval($line);
							echo "<option value=\"$graph_domain_num_days\">the last $graph_domain_num_days days</option>\n"; 
						}
					}
				?>
			</select>
			<br>
			<br>
			<?php
				if($is_main_page_dynamic) {
					echo 'Graph end date: <br>
					<input id="end_date_field" type="text" value="today"></input>
					<br>
					<br>';
				}
			?>
			<?php
				if($is_main_page_dynamic) {
					echo '<button onclick="update_img_from_gui_controls()">Update</button>
					<br>
					<br>';
				}
			?>
			</div>
			<div style="float: right;">
				<img src="blank_1x629.gif">
			</div>
			<div style="float: right; overflow:scroll; width:1200px;">
				<img id="img_graph" src="">
			</div>
			<br style="clear: both;" />
		</div>
		<br>
		<div>
			<div style="float: left;">
				<p id="p_info"/>
			</div>
			<div style="float: right; visibility:hidden;">
				1<br> 2<br> 3<br> 4<br> 5<br> 6<br> 7<br> 8<br> 9<br> 10<br>
				1<br> 2<br> 3<br> 4<br> 5<br> 6<br> 7<br> 8<br> 9<br> 10<br>
			</div>
		</div>
	</body>
</html>
