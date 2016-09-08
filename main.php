<!DOCTYPE html>
<html>
	<head>
	<script src="jquery-3.1.0.min.js"></script>
	<script src="sprintf.min.js"></script>
	<script type="text/javascript">

var WEATHER_CHANNEL_TO_LONG_MULTILINE_NAME = <?php readfile('WEATHER_CHANNEL_TO_LONG_MULTILINE_NAME.json');?>

var WEATHER_CHANNEL_TO_SINGLE_LINE_NAME = {};
for(var channel in WEATHER_CHANNEL_TO_LONG_MULTILINE_NAME) {
	var multiline_name = WEATHER_CHANNEL_TO_LONG_MULTILINE_NAME[channel];
	var single_line_name = multiline_name.replace('\n', ' ');
	WEATHER_CHANNEL_TO_SINGLE_LINE_NAME[channel] = single_line_name;
}

function initialize() {
	update_img_from_controls();
}

function update_img_from_controls() {
	var target_time = $("#target_time_list").val();
	var weather_check_num_hours = $("#weather_check_num_hours_list").val();
	var end_date = $("#end_date_field").val();
	var num_days = $("#num_days_field").val();
	update_img(target_time, weather_check_num_hours, end_date, num_days);
}

function update_img(target_time_, weather_check_num_hours_, end_date_, num_days_) {
	var url = get_img_url(target_time_, weather_check_num_hours_, end_date_, num_days_);
	$("#img_graph").attr("src", "loading.gif");
	$("#p_scores").html('');
	$.ajax({url:url, async:true, 
		error: function(jqXHR__, textStatus__, errorThrown__) {
			$("#img_graph").attr("src", "error.png");
		}, 
		success: function(data__, textStatus__, jqXHR__) {
			$("#img_graph").attr("src", "");
			var png_content_base64 = data__['png'];
			var inline_img = "data:image/png;base64,"+png_content_base64;
			$("#img_graph").attr("src", inline_img);
			update_p_scores(data__['channel_to_score']);
		}
	});
}

function update_p_scores(channel_to_score_) {
	var html = '<h3>"Mean Squared Error" score for each forecast source:<br>(Lower score = more accurate)</h3><br>';
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
	channels.forEach(function(channel) {
		var score = channel_to_score_[channel];
		var channel_long_name = WEATHER_CHANNEL_TO_SINGLE_LINE_NAME[channel];
		html += sprintf('%s: %s<br>', channel_long_name, score);
	});
	$("#p_scores").html(html);
}

function get_img_url(target_time_, weather_check_num_hours_, end_date_, num_days_) {
	return sprintf("get_graph_info.wsgi?target_time_of_day=%s&weather_check_num_hours_in_advance=%s&end_date=%s&num_days=%s", 
			target_time_, weather_check_num_hours_, end_date_, num_days_);
}

$(document).ready(initialize);

	</script>
	</head>
	<body>
		<h2>Wind forecasts vs. actual wind<br>Toronto Islands</h2>
		<br>
		What time of day do you sail? 
		<select id="target_time_list" required>
			<option value="08">8:00 AM</option>
			<option value="11">11:00 AM</option>
			<option value="14">2:00 PM</option>
			<option value="17" selected="selected">5:00 PM</option>
			<option value="20">8:00 PM</option>
		</select>
		<br>
		<br>
		When do you check the forecast? 
		<select id="weather_check_num_hours_list" required>
			<option value="2">2 hours in advance</option>
			<option value="4" selected="selected">4 hours in advance</option>
			<option value="8">8 hours in advance</option>
			<option value="12">12 hours in advance</option>
			<option value="16">16 hours in advance</option>
			<option value="20">20 hours in advance</option>
			<option value="24">24 hours in advance</option>
			<option value="36">36 hours in advance</option>
			<option value="48">48 hours in advance</option>
			<option value="72">3 days in advance</option>
			<option value="96">4 days in advance</option>
			<option value="120">5 days in advance</option>
			<option value="144">6 days in advance</option>
			<option value="168">7 days in advance</option>
		</select>
		<br>
		<br>
		Graph end date: <input id="end_date_field" type="text" value="today"></input>
		<br>
		<br>
		Number of days to graph: <input id="num_days_field" type="text" value="7"></input>
		<br>
		<br>
		<button onclick="update_img_from_controls()">Submit</button>
		<br>
		<br>
		<img id="img_graph" src="">
		<p id="p_scores"/>
	</body>
</html>
