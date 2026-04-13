<?php
/**
 * Settings page — API key, model selection, endpoint override.
 */

defined( 'ABSPATH' ) || exit;

add_action( 'admin_init', 'wam_register_settings' );

function wam_register_settings() {
    register_setting( 'wam_settings', 'wam_openai_api_key',  [ 'sanitize_callback' => 'sanitize_text_field' ] );
    register_setting( 'wam_settings', 'wam_model',           [ 'sanitize_callback' => 'sanitize_text_field', 'default' => 'gpt-4o-mini' ] );
    register_setting( 'wam_settings', 'wam_api_endpoint',    [ 'sanitize_callback' => 'esc_url_raw', 'default' => WAM_DEFAULT_ENDPOINT ] );
}

function wam_render_settings_page() {
    if ( ! current_user_can( 'manage_options' ) ) {
        return;
    }
    ?>
    <div class="wrap">
        <h1>AI Manager — Settings</h1>
        <form method="post" action="options.php">
            <?php settings_fields( 'wam_settings' ); ?>
            <table class="form-table" role="presentation">

                <tr>
                    <th scope="row"><label for="wam_openai_api_key">OpenAI API Key</label></th>
                    <td>
                        <input type="password"
                               id="wam_openai_api_key"
                               name="wam_openai_api_key"
                               value="<?php echo esc_attr( get_option( 'wam_openai_api_key', '' ) ); ?>"
                               class="regular-text"
                               autocomplete="off" />
                        <p class="description">
                            Get your key at <a href="https://platform.openai.com/api-keys" target="_blank" rel="noopener">platform.openai.com/api-keys</a>.
                            It is stored in your database and never sent to anyone except OpenAI.
                        </p>
                    </td>
                </tr>

                <tr>
                    <th scope="row"><label for="wam_model">Model</label></th>
                    <td>
                        <select id="wam_model" name="wam_model">
                            <?php
                            $current = get_option( 'wam_model', 'gpt-4o-mini' );
                            $models  = [
                                'gpt-4o-mini' => 'GPT-4o mini (fast, cheap — recommended)',
                                'gpt-4o'      => 'GPT-4o (smarter, costs more)',
                            ];
                            foreach ( $models as $value => $label ) {
                                printf(
                                    '<option value="%s" %s>%s</option>',
                                    esc_attr( $value ),
                                    selected( $current, $value, false ),
                                    esc_html( $label )
                                );
                            }
                            ?>
                        </select>
                    </td>
                </tr>

                <tr>
                    <th scope="row"><label for="wam_api_endpoint">API Endpoint</label></th>
                    <td>
                        <input type="url"
                               id="wam_api_endpoint"
                               name="wam_api_endpoint"
                               value="<?php echo esc_attr( get_option( 'wam_api_endpoint', WAM_DEFAULT_ENDPOINT ) ); ?>"
                               class="regular-text" />
                        <p class="description">Leave as default unless you are using a custom backend.</p>
                    </td>
                </tr>

            </table>
            <?php submit_button( 'Save Settings' ); ?>
        </form>

        <?php wam_render_connection_test(); ?>
    </div>
    <?php
}

function wam_render_connection_test() {
    $api_key = get_option( 'wam_openai_api_key', '' );
    if ( ! $api_key ) {
        return;
    }
    echo '<hr><h2>Connection Test</h2>';
    echo '<p><a href="' . esc_url( admin_url( 'admin.php?page=wam-settings&wam_test=1' ) ) . '" class="button">Test API Key</a></p>';

    if ( isset( $_GET['wam_test'] ) && current_user_can( 'manage_options' ) ) {
        $result = wam_chat( 'Reply with exactly: "Connection OK"' );
        if ( is_wp_error( $result ) ) {
            echo '<div class="notice notice-error inline"><p>' . esc_html( $result->get_error_message() ) . '</p></div>';
        } else {
            echo '<div class="notice notice-success inline"><p>API connected. Response: <strong>' . esc_html( $result ) . '</strong></p></div>';
        }
    }
}
