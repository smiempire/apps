function bindTimeRange() {
    var fromTime, toTime = '';
    var toDate = $('#id_route_departure_date_from_0').val();
    var timeRange = $('#time_range').val();
    switch (timeRange) {
        case 'none':
            toDate = '';
            break;
        case 'morning':
            fromTime = '04:00:00';
            toTime = '12:00:00';
            break;
        case 'day':
            fromTime = '12:00:00';
            toTime = '16:00:00';
            break;
        case 'evening':
            fromTime = '16:00:00';
            toTime = '23:50:00';
            break;
        case 'night':
            fromTime = '00:00:00';
            toTime = '04:00:00';
            break;
    }
    $('#id_route_departure_date_to_0').val(toDate);
    $('#id_route_departure_time_from_0').val(fromTime);
    $('#id_route_departure_time_to_0').val(toTime);
}

function bindAdrComponent(element, place, component) {
    var value = $('#' + element).val();
    $('#id_' + place + '_' + component).val(value);
}

function parseRoute() {
    var url = $('#id_post_url').val();
    var data = {
        'url': url
    };
    $.ajax({
        url: '/1/utils/vk_post_parsing.json',
        data: data,
        type: 'POST',
        dataType : 'json',
        success: function (data) {
            if (data) {
                $('#id_post_text').val(data['text']);

                $('#id_user_first_name').val(data['user_first_name']);
                $('#id_user_last_name').val(data['user_last_name']);
                $('#id_user_sex').val(data['user_sex']);
                $('#id_user_phone').val(data['user_phone']);
                $('#id_user_vk_profile_url').val(data['user_url']);

                $('#id_route_role').val(data['route_role']);
                $('#id_route_departure_date_from_0').val(data['route_date']);
                $('#time_range').val(data['route_time_range']);
                bindTimeRange();
                $('#id_route_cost').val(data['route_cost']);
                $('#id_route_passengers_count').val(data['route_passengers_count']);
                $('#id_start_place_locality').val(data['route_start']);
                $('#id_finish_place_locality').val(data['route_finish']);
            } else {
                alert('Не удалость распарсить пост.')
            }
        }
    });

}
