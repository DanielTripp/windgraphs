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

function initialize() {
	init_gui_controls();
	update_view_from_gui_controls();
}

function init_gui_controls() {
	["#target_time_list", "#weather_check_num_hours_list", "#stats_time_frame_days_list"].forEach(function(ctrl_name) {
		var oldVal = sessionStorage.getItem(ctrl_name);
		if(oldVal != null) {
			$(ctrl_name).val(oldVal);
		}
		<?php if(!$is_main_page_dynamic) { ?>
			$(ctrl_name).change(on_gui_control_changed);
		<?php } ?>
	});
}

function on_gui_control_changed() {
	update_view_from_gui_controls();
}

function write_gui_control_values_to_storage() {
	["#target_time_list", "#weather_check_num_hours_list", "#stats_time_frame_days_list"].forEach(function(ctrl_name) {
		sessionStorage.setItem(ctrl_name, $(ctrl_name).val());
	});
}

function update_view_from_gui_controls() {
	write_gui_control_values_to_storage();
	var target_time = $("#target_time_list").val();
	var weather_check_num_hours = $("#weather_check_num_hours_list").val();
	<?php
		if($is_main_page_dynamic) {
			echo 'var end_date = $("#end_date_field").val();';
		} else {
			echo 'var end_date = null;';
		}
	?>
	var num_days = $("#stats_time_frame_days_list").val();
	update_view(target_time, weather_check_num_hours, end_date, num_days);
}

function update_view(target_time_, weather_check_num_hours_, end_date_, num_days_) {
	var url = get_img_url(target_time_, weather_check_num_hours_, end_date_, num_days_);
	var y_scroll_pos = $(window).scrollTop();
	$("#img_loading").attr("src", "loading.gif");
	$("#p_info").html('');
	$.ajax({url:url, async:true, 
		error: function(jqXHR__, textStatus__, errorThrown__) {
			$("#img_loading").attr("src", "error.png");
			update_p_info_with_error(textStatus__, errorThrown__);
		}, 
		success: function(data__, textStatus__, jqXHR__) {
			$("#img_loading").attr("src", "");
			update_p_info(data__['html']);
			$(window).scrollTop(y_scroll_pos);
		}
	});
}

function get_legend_observation_img_filename() {
	return 'img/observations.png';
}

function get_legend_forecast_img_filename(channel_) {
	return sprintf('img/%s.png', channel_);
}

function update_p_info_with_error(text_status_, error_thrown_) {
	var html = sprintf('<pre>%s\n%s</pre>', text_status_, error_thrown_);
	$("#p_info").html(html);
}

function update_p_info(html_) {
	$("#p_info").html(html_);
}

function get_img_url(target_time_, weather_check_num_hours_, end_date_, num_days_) {
	<?php 
		if($is_main_page_dynamic) {
			echo 'return sprintf("get_data.wsgi?target_time_of_day=%s&weather_check_num_hours_in_advance=%s&end_date=%s&num_days=%s", 
					target_time_, weather_check_num_hours_, end_date_, num_days_);';
		} else {
			echo 'return sprintf("generated_data_files/data___target_time_%02d___hours_in_advance_%d___stats_time_frame_days_%d.json", 
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
			What time of day do you sail? 
			<select id="target_time_list" required>
				<?php 
					foreach(explode("\n", file_get_contents('config/target_times.txt')) as $line) {
						if($line != "") {
							$hour_24_str = $line;
							$hour = intval($line); 
							if($hour == -1) {
								$display_str = "Any time of day";
							} else if($hour > 12) {
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
			When do you check the forecast? 
			<select id="weather_check_num_hours_list" required>
				<?php 
					foreach(explode("\n", file_get_contents('config/hours_in_advance.txt')) as $line) {
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
			Show data for: 
			<select id="stats_time_frame_days_list" required>
				<?php 
					foreach(explode("\n", file_get_contents('config/stats_time_frame_days.txt')) as $line) {
						if($line != "") {
							$stats_time_frame_days = intval($line);
							echo "<option value=\"$stats_time_frame_days\">the last $stats_time_frame_days days</option>\n"; 
						}
					}
				?>
			</select>
			<br>
			<br>
			<?php
				if($is_main_page_dynamic) {
					echo 'Graph end date (In yyyymmdd format, or "today"): 
					<input id="end_date_field" type="text" value="today"></input>
					<br>
					<br>';
				}
			?>
			<?php
				if($is_main_page_dynamic) {
					echo '<button onclick="update_view_from_gui_controls()">Update</button>
					<br>
					<br>';
				}
			?>
		</div>
		<div>
			<div style="float: left;">
				<br>
				<img id="img_loading" src="">
				<p id="p_info"/>
			</div>
		</div>
	</body>
</html>
